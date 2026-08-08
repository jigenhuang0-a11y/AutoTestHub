"""
审计日志 — 全量记录工具调用

记录内容：
- 调用人（user_id）/ 团队（team_id）
- 工具名 + 参数（脱敏后的）
- 调用时间 / 耗时
- 执行结果（成功/失败）
- 风险等级
"""
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 审计专用 logger（可单独配置输出到审计日志文件）
audit_logger = logging.getLogger("tool_audit")
audit_logger.propagate = False  # 不传到根 logger


@dataclass
class AuditRecord:
    """单次工具调用审计记录"""
    trace_id: str
    tool_name: str
    category: str
    team_id: Optional[str]
    user_id: Optional[int]
    arguments: dict  # 脱敏后的参数
    risk_level: str
    status: str  # "success" | "error" | "denied"
    error_message: Optional[str] = None
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    def to_log_line(self) -> str:
        """转为一行日志（方便 grep）"""
        return (
            f"[AUDIT] trace={self.trace_id} team={self.team_id} user={self.user_id} "
            f"tool={self.tool_name} risk={self.risk_level} status={self.status} "
            f"duration={self.duration_ms}ms"
            + (f" error={self.error_message[:100]}" if self.error_message else "")
        )


class AuditLogger:
    """
    工具调用审计日志

    支持：
    - 内存缓存（开发/测试用）
    - 文件日志（生产用，通过 tool_audit logger）
    - 等 Phase 3.4 长期记忆完成后，可扩展写入审计专用记忆

    示例：
        auditor = AuditLogger(max_in_memory=1000)
        auditor.record(tool_name="knowledge_search", team_id="team_a",
                       user_id=1, arguments={"query": "***"}, ...)
    """

    def __init__(self, max_in_memory: int = 1000, log_to_file: bool = True):
        self._records: list[AuditRecord] = []
        self._max = max_in_memory
        self._log_to_file = log_to_file

    def record(
        self,
        trace_id: str,
        tool_name: str,
        category: str,
        risk_level: str,
        status: str,
        arguments: dict = None,
        team_id: str = None,
        user_id: int = None,
        error_message: str = None,
        duration_ms: int = 0,
    ) -> AuditRecord:
        """记录一次工具调用"""
        # 参数脱敏
        safe_args = self._sanitize_arguments(arguments or {})

        record = AuditRecord(
            trace_id=trace_id,
            tool_name=tool_name,
            category=category,
            team_id=team_id,
            user_id=user_id,
            arguments=safe_args,
            risk_level=risk_level,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
        )

        # 内存缓存
        self._records.append(record)
        if len(self._records) > self._max:
            self._records = self._records[-self._max:]

        # 文件日志
        if self._log_to_file:
            audit_logger.info(record.to_log_line())
            if status == "error" and error_message:
                audit_logger.error(record.to_log_line())
            elif status == "denied":
                audit_logger.warning(record.to_log_line())

        return record

    def _sanitize_arguments(self, args: dict) -> dict:
        """参数脱敏：移除敏感字段"""
        sensitive_keys = {"password", "token", "secret", "api_key", "authorization", "auth"}
        safe = {}
        for k, v in args.items():
            if k.lower() in sensitive_keys:
                safe[k] = "***REDACTED***"
            elif isinstance(v, str) and len(v) > 500:
                safe[k] = v[:500] + "..."
            else:
                safe[k] = v
        return safe

    def get_records(
        self,
        team_id: str = None,
        tool_name: str = None,
        limit: int = 100,
    ) -> list[dict]:
        """查询审计记录"""
        result = []
        for r in reversed(self._records):
            if team_id and r.team_id != team_id:
                continue
            if tool_name and r.tool_name != tool_name:
                continue
            result.append(r.to_dict())
            if len(result) >= limit:
                break
        return result

    def stats(self, team_id: str = None) -> dict:
        """审计统计"""
        total = 0
        success = 0
        errors = 0
        denied = 0
        by_tool: dict[str, int] = {}

        for r in self._records:
            if team_id and r.team_id != team_id:
                continue
            total += 1
            if r.status == "success":
                success += 1
            elif r.status == "error":
                errors += 1
            elif r.status == "denied":
                denied += 1
            by_tool[r.tool_name] = by_tool.get(r.tool_name, 0) + 1

        return {
            "total": total,
            "success": success,
            "errors": errors,
            "denied": denied,
            "by_tool": by_tool,
        }

    def health(self) -> dict:
        """健康检查"""
        return {
            "records_in_memory": len(self._records),
            "max_in_memory": self._max,
            "log_to_file": self._log_to_file,
        }
