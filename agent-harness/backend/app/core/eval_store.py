"""
评测结果本地存储

用于缓存 Judge LLM 对每次 LLM 调用的多维度评分，保证"全链路评测中心"页面
即使在不稳定的网络环境下也能稳定展示实时监控数据。

数据同时会写入 Langfuse Score，本地存储只是兜底/聚合用途。
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "eval_scores.json",
)


def _parse_iso(value: str) -> datetime:
    """兼容 Python 3.10/3.11 的 ISO 时间解析。"""
    if not value:
        return datetime.min
    # Python 3.10 不支持末尾 Z，先替换
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class EvalStore:
    """线程安全的 JSON 文件存储。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ensure_db()

    def _ensure_db(self):
        if not self.db_path.exists():
            self._write({"records": []})

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[EvalStore] 读取失败: {e}，返回空数据集")
            return {"records": []}

    def _write(self, data: Dict[str, Any]):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save(self, record: Dict[str, Any]) -> str:
        """保存一条评测记录，返回 record_id。写入失败直接抛异常，避免前端误判。"""
        record_id = record.get("trace_id") or f"local-{int(time.time() * 1000)}"
        record["record_id"] = record_id
        if "created_at" not in record:
            # 统一使用 UTC，避免服务器时区不一致导致前端显示错乱
            record["created_at"] = datetime.now(timezone.utc).isoformat()

        with self._lock:
            data = self._read()
            # 去重：同 trace_id 覆盖
            data["records"] = [r for r in data["records"] if r.get("record_id") != record_id]
            data["records"].insert(0, record)
            # 最多保留 2000 条，避免文件过大
            data["records"] = data["records"][:2000]
            self._write(data)
        logger.info(f"[EvalStore] 已保存评测记录 {record_id}，当前共 {len(data['records'])} 条")
        return record_id

    def list_records(
        self,
        feature: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            data = self._read()
        records = data.get("records", [])
        if feature:
            records = [r for r in records if r.get("feature") == feature]
        if hours:
            cutoff = datetime.now() - timedelta(hours=hours)
            records = [
                r for r in records
                if _parse_iso(r.get("created_at", "1970-01-01T00:00:00")) >= cutoff
            ]
        return records[offset : offset + limit]

    def get_dashboard(self, hours: int = 24, granularity: str = "auto") -> Dict[str, Any]:
        """聚合仪表盘数据。

        granularity:
          - 'hour': 按小时聚合（默认 24h 窗口内最多 24 个点）
          - 'day' : 按天聚合（适合跨天拉长曲线）
          - 'auto': 若指定 hours 窗口内只有 1 个时间点，则自动退化为 'day'，
                    让趋势曲线更完整；否则用 'hour'。
        """
        records = self.list_records(hours=hours, limit=10000)
        total = len(records)
        if total == 0:
            return {
                "total_records": 0,
                "granularity": "hour",
                # 空数据也返回粒度，前端好判断
                "avg_scores": {"overall": 0, "hallucination": 0, "consistency": 0,
                               "completeness": 0, "executability": 0, "safety": 0},
                "by_feature": {},
                "trend": [],
                "recent_records": [],
            }

        dims = ["hallucination", "consistency", "completeness", "executability", "safety"]
        avg_scores = {"overall": round(sum(r.get("overall", 0) for r in records) / total, 2)}
        for dim in dims:
            avg_scores[dim] = round(sum(r.get(dim, 0) for r in records) / total, 2)

        # 按 feature 聚合
        by_feature: Dict[str, Dict[str, Any]] = {}
        for r in records:
            feat = r.get("feature", "unknown")
            if feat not in by_feature:
                by_feature[feat] = {"count": 0, "overall_sum": 0.0}
            by_feature[feat]["count"] += 1
            by_feature[feat]["overall_sum"] += r.get("overall", 0)
        for feat in by_feature:
            by_feature[feat]["avg_overall"] = round(
                by_feature[feat]["overall_sum"] / by_feature[feat]["count"], 2
            )
            del by_feature[feat]["overall_sum"]

        # 智能粒度：auto 时，若窗口内只有 1 个时间点，退化为按天聚合
        effective_gran = granularity
        if effective_gran == "auto":
            # 先按小时聚合看有几个点
            hour_map: Dict[str, int] = {}
            for r in records:
                hour = r.get("created_at", "")[:13]
                hour_map[hour] = hour_map.get(hour, 0) + 1
            effective_gran = "day" if len(hour_map) <= 1 else "hour"

        # 按粒度聚合趋势
        trend_map: Dict[str, Dict[str, Any]] = {}
        for r in records:
            if effective_gran == "day":
                key = r.get("created_at", "")[:10]        # '2026-08-16'
            else:
                key = r.get("created_at", "")[:13]        # '2026-08-16T14'
            if key not in trend_map:
                trend_map[key] = {"hour": key, "count": 0, "overall_sum": 0.0}
            trend_map[key]["count"] += 1
            trend_map[key]["overall_sum"] += r.get("overall", 0)
        trend = sorted(trend_map.values(), key=lambda x: x["hour"])
        # 小时粒度最多展示最近 24 个点，避免过宽
        if effective_gran == "hour":
            trend = trend[-24:]
        for t in trend:
            t["avg_overall"] = round(t["overall_sum"] / t["count"], 2)
            del t["overall_sum"]

        return {
            "total_records": total,
            "granularity": effective_gran,
            "avg_scores": avg_scores,
            "by_feature": by_feature,
            "trend": trend,
            "recent_records": records[:20],
        }


_eval_store: Optional[EvalStore] = None


def get_eval_store() -> EvalStore:
    global _eval_store
    if _eval_store is None:
        _eval_store = EvalStore()
    return _eval_store
