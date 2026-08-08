"""
自主纠错引擎 (Self-Healing Engine)
-- 编排服务版本 --

从 Django Harness 迁入，无 Django 依赖，LLM 调用走 ai-orchestration-service 的 router。

核心能力:
1. 错误分类 — 识别错误类型（网络、断言、超时、语法、数据、环境）
2. 策略选择 — 基于错误类型选择修复策略
3. 自动修复 — 执行修复策略并验证
4. 历史学习 — 记录修复历史，避免重复尝试无效策略

架构:
    Error → 分类器 → 策略选择 → 修复执行 → 验证 → 记录
                  ↑__________________________↓ (重试 n 次)
"""

import json
import logging
import re
import time
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================
# 错误分类枚举
# ============================================================

class ErrorCategory(str, Enum):
    """错误类别"""
    NETWORK = "network"       # 网络错误: 连接超时、DNS、502/503
    TIMEOUT = "timeout"       # 超时: 请求/响应超时
    ASSERTION = "assertion"   # 断言失败: 预期与实际不符
    SYNTAX = "syntax"         # 语法错误: JSON/代码/模板错误
    DATA = "data"             # 数据错误: 缺失字段、类型不符、数据污染
    AUTH = "auth"             # 认证错误: 401/403、Token 过期
    ENVIRONMENT = "environment"  # 环境错误: 服务不可用、配置错误
    LLM = "llm"               # LLM 错误: API 限流、内容过滤、幻觉
    UNKNOWN = "unknown"       # 未知错误


class Severity(str, Enum):
    """严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorAnalysis:
    """错误分析结果"""
    category: ErrorCategory
    severity: Severity
    summary: str
    root_cause: str
    fixable: bool
    suggested_strategies: list
    raw_error: str = ""
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "summary": self.summary,
            "root_cause": self.root_cause,
            "fixable": self.fixable,
            "suggested_strategies": self.suggested_strategies,
        }


@dataclass
class HealingRecord:
    """修复记录"""
    id: str
    step_name: str
    error_analysis: ErrorAnalysis
    strategy_used: str
    success: bool
    attempts: int
    duration_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""


# ============================================================
# 错误分类器
# ============================================================

class ErrorClassifier:
    """错误分类器 — 基于规则 + AI 的错误识别"""

    PATTERNS = {
        ErrorCategory.NETWORK: [
            r"(?i)(connection\s*(refused|reset|timeout|error|aborted))",
            r"(?i)(dns\s*(resolution|lookup|failure|error))",
            r"(?i)(socket\s*(error|hangup|timeout))",
            r"(?i)(ECONNREFUSED|ECONNRESET|EHOSTUNREACH|ENOTFOUND)",
            r"(?i)(50[23]\s*(service\s*unavailable|bad\s*gateway))",
            r"(?i)(cannot\s*(connect|reach|resolve))",
        ],
        ErrorCategory.TIMEOUT: [
            r"(?i)(timeout|timed?\s*out)",
            r"(?i)(request\s*(timeout|expired))",
            r"(?i)(ETIMEDOUT|ESOCKETTIMEDOUT)",
        ],
        ErrorCategory.ASSERTION: [
            r"(?i)(assert\s*(failed|error))",
            r"(?i)(expected.*but.*(got|found|actual|received))",
            r"(?i)(assertionerror)",
            r"(?i)(does\s*not\s*match|is\s*not\s*equal|should\s*be)",
            r"(?i)(校验失败|断言失败|与预期不符)",
        ],
        ErrorCategory.SYNTAX: [
            r"(?i)(syntax\s*error|parse\s*error|parsing\s*failed)",
            r"(?i)(invalid\s*(json|syntax|format|yaml|xml))",
            r"(?i)(unexpected\s*(token|character|end|EOF))",
            r"(?i)(jsondecodeerror)",
            r"(?i)(语法错误|格式错误|解析失败)",
        ],
        ErrorCategory.DATA: [
            r"(?i)(key\s*error|keyerror|missing\s*(field|parameter|argument))",
            r"(?i)(type\s*error|typeerror|attribute\s*error)",
            r"(?i)(none\s*type|nonetype|null\s*pointer)",
            r"(?i)(index\s*error|indexerror|out\s*of\s*range)",
            r"(?i)(value\s*error|valueerror)",
        ],
        ErrorCategory.AUTH: [
            r"(?i)(401|403|unauthenticated|forbidden|unauthorized)",
            r"(?i)(token\s*(expired|invalid|missing|revoked))",
            r"(?i)(auth\s*(failed|error|required))",
            r"(?i)(permission\s*denied|access\s*denied)",
        ],
        ErrorCategory.ENVIRONMENT: [
            r"(?i)(service\s*(unavailable|down|not\s*found))",
            r"(?i)(configuration\s*error|config\s*error|misconfiguration)",
            r"(?i)(environment\s*(variable|not\s*set|missing))",
        ],
        ErrorCategory.LLM: [
            r"(?i)(rate\s*limit|too\s*many\s*requests|quota\s*exceeded)",
            r"(?i)(content\s*filter|safety\s*system|content\s*policy)",
            r"(?i)(max\s*tokens|context\s*length|token\s*limit)",
            r"(?i)(model\s*(overloaded|unavailable|not\s*found))",
        ],
    }

    @classmethod
    def classify(cls, error: str, context: dict = None) -> ErrorAnalysis:
        """分类一个错误"""
        if not error or not error.strip():
            return ErrorAnalysis(
                category=ErrorCategory.UNKNOWN, severity=Severity.LOW,
                summary="空错误消息", root_cause="未提供错误信息",
                fixable=False, suggested_strategies=["retry"],
                raw_error=error, context=context or {},
            )

        category = ErrorCategory.UNKNOWN
        for cat, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error):
                    category = cat
                    break
            if category != ErrorCategory.UNKNOWN:
                break

        severity = cls._judge_severity(category)
        fixable = category not in [ErrorCategory.ENVIRONMENT, ErrorCategory.AUTH]
        strategies = cls._suggest_strategies(category)

        return ErrorAnalysis(
            category=category, severity=severity,
            summary=cls._summarize(category, error),
            root_cause=cls._root_cause(category),
            fixable=fixable, suggested_strategies=strategies,
            raw_error=error, context=context or {},
        )

    @classmethod
    def classify_with_ai(cls, error: str, context: dict = None) -> ErrorAnalysis:
        """使用 LLM 做深度分类（编排服务版）"""
        analysis = cls.classify(error, context)
        if analysis.category != ErrorCategory.UNKNOWN:
            return analysis

        try:
            from app.core.router import get_llm_router
            router = get_llm_router()
            prompt = f"""分析以下错误并分类 (只返回JSON):
错误: {error}
上下文: {json.dumps(context or {}, ensure_ascii=False)}

{{"category": "network|timeout|assertion|syntax|data|auth|environment|llm|unknown", "severity": "low|medium|high|critical", "summary": "...", "root_cause": "...", "fixable": true|false, "suggested_strategies": ["策略"]}}"""
            response = router.chat(messages=[{"role": "user", "content": prompt}], task_type="analysis")
            j = response.find("{")
            if j >= 0:
                d = json.loads(response[j:response.rfind("}")+1])
                return ErrorAnalysis(
                    category=ErrorCategory(d.get("category", "unknown")),
                    severity=Severity(d.get("severity", "medium")),
                    summary=d.get("summary", error[:100]),
                    root_cause=d.get("root_cause", ""),
                    fixable=d.get("fixable", False),
                    suggested_strategies=d.get("suggested_strategies", ["retry"]),
                    raw_error=error, context=context or {},
                )
        except Exception as e:
            logger.warning(f"[SelfHealing] AI分类失败: {e}")

        return analysis

    @classmethod
    def _judge_severity(cls, category):
        m = {ErrorCategory.AUTH: Severity.HIGH, ErrorCategory.ENVIRONMENT: Severity.CRITICAL,
             ErrorCategory.NETWORK: Severity.MEDIUM, ErrorCategory.TIMEOUT: Severity.LOW}
        return m.get(category, Severity.MEDIUM)

    @classmethod
    def _summarize(cls, category, error):
        base = {ErrorCategory.NETWORK: "网络异常", ErrorCategory.TIMEOUT: "超时",
                ErrorCategory.ASSERTION: "断言失败", ErrorCategory.SYNTAX: "语法错误",
                ErrorCategory.DATA: "数据异常", ErrorCategory.AUTH: "认证失败",
                ErrorCategory.ENVIRONMENT: "环境异常", ErrorCategory.LLM: "AI异常",
                ErrorCategory.UNKNOWN: "未知错误"}.get(category, "未知")
        return f"{base}: {error[:80].replace(chr(10), ' ')}"

    @classmethod
    def _root_cause(cls, category):
        return {ErrorCategory.NETWORK: "服务不可达", ErrorCategory.TIMEOUT: "负载过高",
                ErrorCategory.ASSERTION: "接口变更或数据不一致", ErrorCategory.SYNTAX: "格式问题",
                ErrorCategory.DATA: "数据缺失或类型不匹配", ErrorCategory.AUTH: "凭据过期",
                ErrorCategory.ENVIRONMENT: "配置错误", ErrorCategory.LLM: "限流或内容拦截",
                ErrorCategory.UNKNOWN: "无法识别"}.get(category, "未知")

    @classmethod
    def _suggest_strategies(cls, category):
        return {ErrorCategory.NETWORK: ["retry_with_backoff", "switch_endpoint"],
                ErrorCategory.TIMEOUT: ["retry_with_backoff", "increase_timeout"],
                ErrorCategory.ASSERTION: ["relax_assertion", "update_expected_value"],
                ErrorCategory.SYNTAX: ["reformat_input", "ai_fix_syntax"],
                ErrorCategory.DATA: ["fill_defaults", "skip_optional_fields"],
                ErrorCategory.AUTH: ["refresh_token"],
                ErrorCategory.ENVIRONMENT: ["verify_config"],
                ErrorCategory.LLM: ["retry_with_backoff", "switch_model"],
                ErrorCategory.UNKNOWN: ["retry", "ai_diagnose"]}.get(category, ["retry"])


# ============================================================
# 修复策略
# ============================================================

class FixStrategy:
    """修复策略基类"""
    name: str = "base"
    description: str = "基础策略"

    def can_handle(self, analysis: ErrorAnalysis) -> bool:
        return True

    def execute(self, step_func: Callable, step_params: dict,
                analysis: ErrorAnalysis, max_attempts: int = 3) -> HealingRecord:
        raise NotImplementedError


class RetryWithBackoff(FixStrategy):
    """指数退避重试"""
    name = "retry_with_backoff"
    description = "指数退避重试 (1s, 2s, 4s...)"

    def can_handle(self, a):
        return a.category in (ErrorCategory.NETWORK, ErrorCategory.TIMEOUT, ErrorCategory.LLM)

    def execute(self, step_func, params, analysis, max_attempts=3):
        start = time.time()
        for attempt in range(1, max_attempts + 1):
            wait = 2 ** (attempt - 1)
            logger.info(f"[SelfHealing] 退避重试 {attempt}/{max_attempts}, 等待{wait}s")
            time.sleep(wait)
            try:
                result = step_func(**params)
                if not self._is_error(result):
                    return HealingRecord(
                        id=f"h-{int(start*1000)}", step_name=params.get("step_name", ""),
                        error_analysis=analysis, strategy_used=self.name, success=True,
                        attempts=attempt, duration_ms=int((time.time()-start)*1000),
                        notes=f"第{attempt}次重试成功")
            except Exception as e:
                logger.warning(f"[SelfHealing] 重试{attempt}失败: {e}")
        return HealingRecord(
            id=f"h-{int(start*1000)}", step_name=params.get("step_name", ""),
            error_analysis=analysis, strategy_used=self.name, success=False,
            attempts=max_attempts, duration_ms=int((time.time()-start)*1000),
            notes="全部重试失败")

    def _is_error(self, r):
        return isinstance(r, dict) and (r.get("status") in ("error", "failed") or r.get("error"))


class AIFixSyntax(FixStrategy):
    """AI 修复语法/格式错误"""
    name = "ai_fix_syntax"
    description = "AI 自动修复语法错误"

    def can_handle(self, a):
        return a.category == ErrorCategory.SYNTAX

    def execute(self, step_func, params, analysis, max_attempts=2):
        start = time.time()
        try:
            from app.core.router import get_llm_router
            router = get_llm_router()
            prompt = f"修复以下内容中的错误:\n{analysis.raw_error[:500]}\n修复后内容:"
            fixed = router.chat(messages=[{"role": "user", "content": prompt}], task_type="fix")
            if "prompt" in params:
                params["prompt"] = fixed
            result = step_func(**params)
            success = not (isinstance(result, dict) and result.get("error"))
            return HealingRecord(
                id=f"h-{int(start*1000)}", step_name=params.get("step_name", ""),
                error_analysis=analysis, strategy_used=self.name, success=success,
                attempts=1, duration_ms=int((time.time()-start)*1000),
                notes="AI修复" if success else "AI修复后仍失败")
        except Exception as e:
            logger.exception(f"[SelfHealing] AI修复异常: {e}")
        return HealingRecord(
            id=f"h-{int(start*1000)}", step_name=params.get("step_name", ""),
            error_analysis=analysis, strategy_used=self.name, success=False,
            attempts=max_attempts, duration_ms=int((time.time()-start)*1000),
            notes="无法修复")


class AIDiagnose(FixStrategy):
    """AI 诊断 + 建议修复"""
    name = "ai_diagnose"
    description = "AI 深度诊断分析"

    def execute(self, step_func, params, analysis, max_attempts=1):
        start = time.time()
        try:
            from app.core.router import get_llm_router
            router = get_llm_router()
            prompt = f"""分析此错误并给出修复方案(JSON):
步骤: {params.get('step_name','')}
错误: {analysis.raw_error[:500]}
{{"diagnosis":"...","fix_suggestion":"...","modified_params":{{}}}}"""
            response = router.chat(messages=[{"role": "user", "content": prompt}], task_type="analysis")
            j = response.find("{")
            if j >= 0:
                diag = json.loads(response[j:response.rfind("}")+1])
                if diag.get("modified_params"):
                    params.update(diag["modified_params"])
                result = step_func(**params)
                success = not (isinstance(result, dict) and result.get("error"))
                return HealingRecord(
                    id=f"h-{int(start*1000)}", step_name=params.get("step_name", ""),
                    error_analysis=analysis, strategy_used=self.name, success=success,
                    attempts=1, duration_ms=int((time.time()-start)*1000),
                    notes=diag.get("fix_suggestion", ""))
        except Exception as e:
            logger.exception(f"[SelfHealing] AI诊断异常: {e}")
        return HealingRecord(
            id=f"h-{int(start*1000)}", step_name=params.get("step_name", ""),
            error_analysis=analysis, strategy_used=self.name, success=False,
            attempts=1, duration_ms=int((time.time()-start)*1000),
            notes="AI诊断后仍无法修复")


# ============================================================
# 自主纠错引擎
# ============================================================

class SelfHealingEngine:
    """
    自主纠错引擎

    流程: 错误捕获 → 分类 → 策略选择 → 修复 → 验证 → 记录

    Usage:
        engine = SelfHealingEngine(max_attempts=3)
        result = engine.heal(step_func=my_func, step_params={"arg": "val"}, step_name="gen")
    """

    def __init__(self, max_attempts: int = 3, use_ai: bool = True):
        self.max_attempts = max_attempts
        self.use_ai = use_ai
        self._strategies: list = [RetryWithBackoff(), AIFixSyntax(), AIDiagnose()]
        self._history: list[HealingRecord] = []
        self._stats = {"total_heals": 0, "successful_heals": 0,
                       "failed_heals": 0, "by_category": {}}

    def heal(self, step_func: Callable, step_params: dict,
             step_name: str = "", context: dict = None) -> dict:
        """自主纠错主入口"""
        ctx = context or {}

        # 首次执行
        try:
            result = step_func(**step_params)
        except Exception as e:
            result = {"status": "error", "error": str(e)}

        if not self._is_error(result):
            return {"status": "success", "result": result,
                    "healing_needed": False, "attempts": 1}

        # 分类
        error_msg = result.get("error", str(result)) if isinstance(result, dict) else str(result)
        analysis = ErrorClassifier.classify(error_msg, {"step_name": step_name, **ctx})
        self._stats["total_heals"] += 1
        self._stats["by_category"][analysis.category.value] = \
            self._stats["by_category"].get(analysis.category.value, 0) + 1

        if not analysis.fixable:
            logger.warning(f"[SelfHealing] 不可修复 [{analysis.category.value}]: {analysis.summary}")
            return {"status": "failed", "result": result, "healing_needed": True,
                    "analysis": analysis.to_dict(), "attempts": 1}

        # 策略执行
        logger.info(f"[SelfHealing] 修复 [{analysis.category.value}]: {analysis.summary}")
        for strategy in self._strategies:
            if not strategy.can_handle(analysis):
                continue
            record = strategy.execute(step_func, step_params, analysis, self.max_attempts)
            self._history.append(record)
            if record.success:
                self._stats["successful_heals"] += 1
                return {"status": "healed", "result": result, "healing_needed": True,
                        "healing_record": record.__dict__,
                        "attempts": record.attempts + 1}

        self._stats["failed_heals"] += 1
        return {"status": "failed", "result": result, "healing_needed": True,
                "analysis": analysis.to_dict(), "attempts": self.max_attempts + 1}

    def _is_error(self, r):
        return isinstance(r, dict) and (r.get("status") in ("error", "failed") or r.get("error"))

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_history(self, limit=20):
        return [h.__dict__ for h in self._history[-limit:]]

    def register_strategy(self, s: FixStrategy):
        self._strategies.append(s)


def create_self_healing_engine(max_attempts=3, use_ai=True) -> SelfHealingEngine:
    return SelfHealingEngine(max_attempts=max_attempts, use_ai=use_ai)
