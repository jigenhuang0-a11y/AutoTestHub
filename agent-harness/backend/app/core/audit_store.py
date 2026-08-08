"""
审计持久化存储 — 所有代码安全检查 + 沙箱执行记录的唯一归口

设计：
- 使用 SQLite（Python 内置，零依赖）存储审计记录
- 支持按 team_id / user_id / task_id / 时间范围查询
- 为审计大屏提供聚合统计接口
- 自动建表、自动清理过期记录（默认保留 90 天）

存储结构：
  audit_events 表：每条审计事件一行
  - id, event_type, severity, team_id, user_id, task_id
  - code_hash, safety_level, safety_passed, safety_issues_json
  - sandbox_status, sandbox_duration_ms, sandbox_stdout
  - created_at
"""

import json
import logging
import sqlite3
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# 数据库路径：与 agent-harness 同级
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
DB_PATH = os.path.join(DB_DIR, "audit.db")

# 数据保留天数
RETENTION_DAYS = 90


class EventType(str, Enum):
    SAFETY_SCAN = "safety_scan"         # 代码安全检查
    SANDBOX_EXEC = "sandbox_exec"       # 沙箱执行
    SANDBOX_TIMEOUT = "sandbox_timeout" # 沙箱超时
    WORKFLOW_START = "workflow_start"   # 工作流开始
    WORKFLOW_END = "workflow_end"       # 工作流结束
    MANUAL_REVIEW = "manual_review"     # 人工审核


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """一条审计事件"""
    id: Optional[int] = None
    event_type: str = ""
    severity: str = "info"
    team_id: str = "default"
    user_id: str = ""
    task_id: str = ""
    code_hash: str = ""
    code_snippet: str = ""            # 代码前100字符（用于展示）
    safety_level: str = ""            # safe / warning / dangerous
    safety_passed: bool = True
    safety_issues: str = "[]"         # JSON
    sandbox_status: str = ""          # success / timeout / error / killed
    sandbox_duration_ms: int = 0
    sandbox_stdout: str = ""          # 前500字符
    sandbox_stderr: str = ""
    workflow_stage: str = ""          # plan / orchestrate / verify
    message: str = ""                 # 人工可读摘要
    created_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("id", None)
        if self.safety_issues:
            try:
                d["safety_issues"] = json.loads(self.safety_issues)
            except json.JSONDecodeError:
                pass
        return d


class AuditStore:
    """审计持久化存储（SQLite）"""

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """确保文本是有效 UTF-8，无效字节替换为 \uFFFD"""
        if not isinstance(text, str):
            text = str(text)
        return text.encode('utf-8', errors='replace').decode('utf-8')

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """建表 + 索引"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL DEFAULT '',
                    severity TEXT NOT NULL DEFAULT 'info',
                    team_id TEXT NOT NULL DEFAULT 'default',
                    user_id TEXT NOT NULL DEFAULT '',
                    task_id TEXT NOT NULL DEFAULT '',
                    code_hash TEXT NOT NULL DEFAULT '',
                    code_snippet TEXT NOT NULL DEFAULT '',
                    safety_level TEXT NOT NULL DEFAULT '',
                    safety_passed INTEGER NOT NULL DEFAULT 1,
                    safety_issues TEXT NOT NULL DEFAULT '[]',
                    sandbox_status TEXT NOT NULL DEFAULT '',
                    sandbox_duration_ms INTEGER NOT NULL DEFAULT 0,
                    sandbox_stdout TEXT NOT NULL DEFAULT '',
                    sandbox_stderr TEXT NOT NULL DEFAULT '',
                    workflow_stage TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                )
            """)
            # 核心索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_team_user ON audit_events(team_id, user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_events(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_safety ON audit_events(safety_level, safety_passed)")
            conn.commit()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA encoding = 'UTF-8'")
        conn.text_factory = lambda b: b.decode('utf-8', errors='replace')
        try:
            yield conn
        finally:
            conn.close()

    def write(self, event: AuditEvent) -> int:
        """写入一条审计事件，返回自增 ID"""
        with self._lock:
            if not event.created_at:
                event.created_at = datetime.now(timezone.utc).isoformat()
            # 清洗所有用户输入文本，防止非 UTF-8 字节存入
            event.message = self._sanitize_text(event.message)
            event.code_snippet = self._sanitize_text(event.code_snippet)
            event.sandbox_stdout = self._sanitize_text(event.sandbox_stdout)
            event.sandbox_stderr = self._sanitize_text(event.sandbox_stderr)
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """INSERT INTO audit_events
                    (event_type, severity, team_id, user_id, task_id,
                     code_hash, code_snippet,
                     safety_level, safety_passed, safety_issues,
                     sandbox_status, sandbox_duration_ms, sandbox_stdout, sandbox_stderr,
                     workflow_stage, message, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        event.event_type, event.severity, event.team_id,
                        event.user_id, event.task_id,
                        event.code_hash, event.code_snippet[:200],
                        event.safety_level,
                        1 if event.safety_passed else 0,
                        event.safety_issues,
                        event.sandbox_status, event.sandbox_duration_ms,
                        event.sandbox_stdout[:1000], event.sandbox_stderr[:500],
                        event.workflow_stage, event.message, event.created_at,
                    ),
                )
                conn.commit()
                event_id = cursor.lastrowid
                logger.debug(f"[AuditStore] 写入事件 id={event_id} type={event.event_type}")
                return event_id

    def write_safety_report(self, task_id: str, user_id: str, team_id: str,
                            code: str, report) -> int:
        """快捷写入：代码安全检查报告"""
        from app.core.code_safety import SafetyReport
        event = AuditEvent(
            event_type=EventType.SAFETY_SCAN.value,
            severity=(
                Severity.CRITICAL.value if not report.passed
                else Severity.WARNING.value if report.level.value == "warning"
                else Severity.INFO.value
            ),
            team_id=team_id,
            user_id=user_id,
            task_id=task_id,
            code_hash=report.code_hash,
            code_snippet=code[:100],
            safety_level=report.level.value,
            safety_passed=report.passed,
            safety_issues=json.dumps(
                [asdict(i) if hasattr(i, '__dataclass_fields__') else i
                 for i in report.issues],
                ensure_ascii=False,
            ),
            message=f"[安全检查] {report.summary()}",
        )
        return self.write(event)

    def write_sandbox_result(self, task_id: str, user_id: str, team_id: str,
                              code_hash: str, status: str, duration_ms: int,
                              stdout: str, stderr: str,
                              safety_level: str = "") -> int:
        """快捷写入：沙箱执行结果"""
        event = AuditEvent(
            event_type=(
                EventType.SANDBOX_TIMEOUT.value if status == "timeout"
                else EventType.SANDBOX_EXEC.value
            ),
            severity=(
                Severity.ERROR.value if status in ("error", "timeout", "killed")
                else Severity.INFO.value
            ),
            team_id=team_id,
            user_id=user_id,
            task_id=task_id,
            code_hash=code_hash,
            safety_level=safety_level,
            sandbox_status=status,
            sandbox_duration_ms=duration_ms,
            sandbox_stdout=stdout[:1000],
            sandbox_stderr=stderr[:500],
            message=f"[沙箱执行] status={status} duration={duration_ms}ms",
        )
        return self.write(event)

    def write_workflow_event(self, task_id: str, user_id: str, team_id: str,
                              stage: str, status: str, message: str) -> int:
        """快捷写入：工作流阶段事件"""
        event = AuditEvent(
            event_type=(
                EventType.WORKFLOW_START.value if status == "start"
                else EventType.WORKFLOW_END.value
            ),
            severity=Severity.INFO.value,
            team_id=team_id,
            user_id=user_id,
            task_id=task_id,
            workflow_stage=stage,
            message=f"[工作流:{stage}] {message}",
        )
        return self.write(event)

    # ── 查询接口 ──

    def query(self, *,
              team_id: str = None,
              user_id: str = None,
              event_type: str = None,
              safety_level: str = None,
              start_date: str = None,
              end_date: str = None,
              limit: int = 50,
              offset: int = 0,
              ) -> list[dict]:
        """通用查询"""
        conditions = []
        params = []

        if team_id:
            conditions.append("team_id = ?")
            params.append(team_id)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if safety_level:
            conditions.append("safety_level = ?")
            params.append(safety_level)
        if start_date:
            conditions.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= ?")
            params.append(end_date)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM audit_events WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def get_stats(self, team_id: str = None, days: int = 7) -> dict:
        """获取统计概览（审计大屏顶部指标）"""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        def _count(sql_extra: str, params: list = None) -> int:
            base = "SELECT COUNT(*) FROM audit_events WHERE created_at >= ?"
            if team_id:
                base += " AND team_id = ?"
            params_full = [since]
            if team_id:
                params_full.append(team_id)
            with self._get_conn() as conn:
                return conn.execute(base + sql_extra, params_full).fetchone()[0]

        return {
            "total_events": _count(""),
            "safety_scans": _count(" AND event_type = 'safety_scan'"),
            "safety_passed": _count(" AND event_type = 'safety_scan' AND safety_passed = 1"),
            "safety_blocked": _count(" AND event_type = 'safety_scan' AND safety_passed = 0"),
            "sandbox_execs": _count(" AND event_type = 'sandbox_exec'"),
            "sandbox_failures": _count(
                " AND event_type IN ('sandbox_exec','sandbox_timeout') AND severity IN ('error','critical')"
            ),
            "period_days": days,
        }

    def get_safety_trend(self, team_id: str = None, days: int = 7) -> dict:
        """安全扫描趋势（按天）"""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        params = [since]
        team_filter = ""
        if team_id:
            team_filter = " AND team_id = ?"
            params.append(team_id)

        sql = """
            SELECT date(created_at) as day,
                   COUNT(*) as total,
                   SUM(CASE WHEN safety_passed = 1 THEN 1 ELSE 0 END) as passed,
                   SUM(CASE WHEN safety_passed = 0 THEN 1 ELSE 0 END) as blocked
            FROM audit_events
            WHERE event_type = 'safety_scan' AND created_at >= ?
        """ + team_filter + """
            GROUP BY date(created_at)
            ORDER BY day ASC
        """

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        dates = []
        passed_vals = []
        blocked_vals = []
        for row in rows:
            dates.append(row["day"])
            passed_vals.append(row["passed"] or 0)
            blocked_vals.append(row["blocked"] or 0)

        return {"dates": dates, "passed": passed_vals, "blocked": blocked_vals}

    def get_risk_distribution(self, team_id: str = None, days: int = 7) -> list[dict]:
        """风险等级分布"""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        params = [since]
        team_filter = ""
        if team_id:
            team_filter = " AND team_id = ?"
            params.append(team_id)

        sql = """
            SELECT safety_level, COUNT(*) as cnt
            FROM audit_events
            WHERE event_type = 'safety_scan' AND created_at >= ?
        """ + team_filter + """
            GROUP BY safety_level
        """
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [{"name": (r["safety_level"] or "unknown"), "value": r["cnt"]} for r in rows]

    def get_recent_events(self, team_id: str = None, limit: int = 20) -> list[dict]:
        """最近审计事件列表"""
        where = "1=1"
        params = []
        if team_id:
            where = "team_id = ?"
            params.append(team_id)

        sql = f"""
            SELECT id, event_type, severity, team_id, user_id, task_id,
                   code_hash, safety_level, safety_passed,
                   sandbox_status, sandbox_duration_ms,
                   workflow_stage, message, created_at
            FROM audit_events
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def cleanup_old_records(self, retention_days: int = RETENTION_DAYS) -> int:
        """清理过期审计记录"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute("DELETE FROM audit_events WHERE created_at < ?", (cutoff,))
                conn.commit()
                deleted = cursor.rowcount
                if deleted:
                    logger.info(f"[AuditStore] 清理过期记录 {deleted} 条（早于 {cutoff}）")
                return deleted


# 全局单例
_audit_store: Optional[AuditStore] = None


def get_audit_store() -> AuditStore:
    """获取全局审计存储"""
    global _audit_store
    if _audit_store is None:
        _audit_store = AuditStore()
    return _audit_store
