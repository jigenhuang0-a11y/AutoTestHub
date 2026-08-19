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
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            records = [
                r for r in records
                if _parse_iso(r.get("created_at", "1970-01-01T00:00:00+00:00")) >= cutoff
            ]
        return records[offset : offset + limit]

    def get_dashboard(self, hours: int = 24, granularity: str = "auto") -> Dict[str, Any]:
        """聚合仪表盘数据。

        granularity:
          - 'hour': 按小时聚合（默认 24h 窗口内 24 个点，空桶补 0）
          - 'week': 按周聚合（适合跨周拉长曲线，空桶补 0）
          - 'auto': 若指定 hours 窗口内只有 1 个时间点，则自动退化为 'week'，
                    让趋势曲线更完整；否则用 'hour'。
        """
        records = self.list_records(hours=hours, limit=10000)
        total = len(records)

        dims = ["hallucination", "consistency", "completeness", "executability", "safety"]
        if total == 0:
            return {
                "total_records": 0,
                "granularity": granularity if granularity != "auto" else "hour",
                "avg_scores": {"overall": 0, "hallucination": 0, "consistency": 0,
                               "completeness": 0, "executability": 0, "safety": 0},
                "by_feature": {},
                "trend": [],
                "recent_records": [],
            }

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

        # 智能粒度：auto 时根据窗口长度选择 hour/week/month
        effective_gran = granularity
        if effective_gran == "auto":
            window_days = hours / 24
            if window_days > 60:
                effective_gran = "month"
            elif window_days > 1:
                effective_gran = "week"
            else:
                effective_gran = "hour"

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)

        def _week_start(dt: datetime) -> datetime:
            return dt - timedelta(days=dt.isoweekday() - 1)

        # 按粒度聚合趋势（只统计窗口内的记录）
        trend_map: Dict[str, Dict[str, Any]] = {}
        for r in records:
            if effective_gran == "month":
                key = r.get("created_at", "")[:7]         # '2026-08'
            elif effective_gran == "week":
                dt = _parse_iso(r.get("created_at", "1970-01-01T00:00:00+00:00"))
                key = _week_start(dt).strftime("%Y-%m-%d")  # 该周周一
            else:
                key = r.get("created_at", "")[:13]        # '2026-08-16T14'
            if key not in trend_map:
                trend_map[key] = {"hour": key, "count": 0, "overall_sum": 0.0, "latest_date": key, "latest_at": r.get("created_at", "")}
            trend_map[key]["count"] += 1
            trend_map[key]["overall_sum"] += r.get("overall", 0)
            # 周/月视图下保留该桶内最新一条记录时间，前端按本地时区显示日期
            if effective_gran in ("week", "month"):
                record_at = r.get("created_at", "")
                if record_at > trend_map[key]["latest_at"]:
                    trend_map[key]["latest_at"] = record_at

        # 填充完整时间窗口，空桶补 None，让 X 轴连续且时间正确
        filled_trend: List[Dict[str, Any]] = []
        if effective_gran == "month":
            def _months_between(a: datetime, b: datetime) -> int:
                return (b.year - a.year) * 12 + (b.month - a.month)

            months = max(1, _months_between(cutoff, now) + 1)
            cur = cutoff.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            for _ in range(months):
                key = cur.strftime("%Y-%m")
                existing = trend_map.get(key, {"hour": key, "count": 0, "overall_sum": 0.0, "latest_date": key, "latest_at": key})
                bucket = existing.copy()
                bucket["hour"] = bucket.get("latest_at") or bucket.get("latest_date") or key
                bucket["avg_overall"] = round(bucket["overall_sum"] / bucket["count"], 2) if bucket["count"] else None
                filled_trend.append(bucket)
                # 下个月
                if cur.month == 12:
                    cur = cur.replace(year=cur.year + 1, month=1)
                else:
                    cur = cur.replace(month=cur.month + 1)
        elif effective_gran == "week":
            start = _week_start(cutoff).replace(hour=0, minute=0, second=0, microsecond=0)
            end = _week_start(now)
            weeks = max(1, (end - start).days // 7 + 1)
            cur = start
            for _ in range(weeks):
                key = cur.strftime("%Y-%m-%d")
                existing = trend_map.get(key, {"hour": key, "count": 0, "overall_sum": 0.0, "latest_date": key, "latest_at": key})
                bucket = existing.copy()
                # X 轴标签显示该周最新有数据时间，空桶则显示周一
                bucket["hour"] = bucket.get("latest_at") or bucket.get("latest_date") or key
                bucket["avg_overall"] = round(bucket["overall_sum"] / bucket["count"], 2) if bucket["count"] else None
                filled_trend.append(bucket)
                cur += timedelta(weeks=1)
        else:
            cur = cutoff.replace(minute=0, second=0, microsecond=0)
            for _ in range(hours + 1):
                key = cur.strftime("%Y-%m-%dT%H")
                bucket = trend_map.get(key, {"hour": key, "count": 0, "overall_sum": 0.0})
                bucket["avg_overall"] = round(bucket["overall_sum"] / bucket["count"], 2) if bucket["count"] else None
                filled_trend.append(bucket)
                cur += timedelta(hours=1)

        for t in filled_trend:
            if "overall_sum" in t:
                del t["overall_sum"]

        return {
            "total_records": total,
            "granularity": effective_gran,
            "avg_scores": avg_scores,
            "by_feature": by_feature,
            "trend": filled_trend,
            "recent_records": records[:20],
        }


_eval_store: Optional[EvalStore] = None


def get_eval_store() -> EvalStore:
    global _eval_store
    if _eval_store is None:
        _eval_store = EvalStore()
    return _eval_store
