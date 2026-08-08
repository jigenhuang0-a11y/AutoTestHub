"""
LLM 输出内容安全过滤器

检测 LLM 输出中的敏感信息泄露：
- API Key / Token 模式
- 内网 IP 地址
- 密钥/凭证模式
- 高熵随机串（疑似未脱敏密钥）

返回 (is_safe, cleaned_text, violations) 三元组。
"""

import re
import math
import logging
from dataclasses import dataclass, field
from collections import Counter

logger = logging.getLogger(__name__)


# ============================================================
# 敏感信息检测规则
# ============================================================

@dataclass
class OutputGuardResult:
    is_safe: bool
    cleaned_text: str = ""
    violations: list[str] = field(default_factory=list)


# 规则集：(正则, 描述, 严重级别)
# critical = 直接替换为 [REDACTED]
# warning = 仅记录日志

SENSITIVE_PATTERNS: list[tuple[str, str, str]] = [
    # === API Key / Token 模式 (critical) ===
    # OpenAI / DeepSeek 格式（含横杠、短前缀如 sk-proj-）
    (r"sk-[a-zA-Z0-9_-]{20,80}", "疑似 OpenAI/DeepSeek API Key", "critical"),
    # GitHub Personal Access Token
    (r"gh[pousr]_[a-zA-Z0-9]{36,}", "疑似 GitHub Token", "critical"),
    # JWT Token
    (r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{10,}", "疑似 JWT Token", "critical"),
    # AWS Access Key
    (r"AKIA[0-9A-Z]{16}", "疑似 AWS Access Key", "critical"),
    # 通用 Token 模式: 前缀_长哈希
    (r"(?:api[_-]?key|access[_-]?token|secret[_-]?key)[=:]\s*['\"]?[a-zA-Z0-9+/=]{20,}['\"]?",
     "疑似明文密钥/Token", "critical"),

    # === 内网地址 (critical) ===
    (r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "内网 IP (10.x)", "critical"),
    (r"\b172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b", "内网 IP (172.16-31.x)", "critical"),
    (r"\b192\.168\.\d{1,3}\.\d{1,3}\b", "内网 IP (192.168.x)", "critical"),
    (r"\b127\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "回环地址 (127.x)", "critical"),

    # === 凭证模式 (critical) ===
    (r"(?:password|passwd|pwd)\s*[=:]\s*['\"]?\S{6,}['\"]?",
     "疑似明文密码", "critical"),
    (r"mongodb(\+srv)?://[^/\s]+@", "MongoDB 连接串含凭证", "critical"),
    (r"postgres(ql)?://[^/\s]+@", "PostgreSQL 连接串含凭证", "critical"),
    (r"redis://[^/\s]+@", "Redis 连接串含凭证", "critical"),
    (r"mysql://[^/\s]+@", "MySQL 连接串含凭证", "critical"),

    # === 个人隐私信息 (warning) ===
    (r"\b1[3-9]\d{9}\b", "手机号码", "warning"),
    (r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", "邮箱地址", "warning"),
    (r"\b\d{17}[\dXx]\b", "身份证号", "warning"),
    (r"\b\d{16,19}\b", "银行卡号", "warning"),
]


class OutputGuard:
    """
    LLM 输出安全守卫

    用法:
        guard = OutputGuard()
        result = guard.scan(llm_response_text)
        return result.cleaned_text  # 安全、脱敏后的文本
    """

    # 高熵阈值（Shannon entropy > 4.2 bit/char 视为可疑）
    ENTROPY_THRESHOLD = 4.2

    def __init__(self, block_critical: bool = True, redact_critical: bool = True):
        """
        Args:
            block_critical: True=严重问题直接拒绝整条回复
            redact_critical: True=严重问题替换为 [REDACTED]（不拒绝）
        """
        self.block_critical = block_critical
        self.redact_critical = redact_critical

    def scan(self, text: str) -> OutputGuardResult:
        """
        扫描 LLM 输出文本，检测并处理敏感信息。

        Returns:
            OutputGuardResult — is_safe=False 表示应拒绝该回复
        """
        violations: list[str] = []
        cleaned = text
        has_critical = False

        for pattern, desc, level in SENSITIVE_PATTERNS:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                log_msg = f"[OutputGuard] 检测到 {desc}: ...{match.group()[:40]}..."
                violations.append(desc)

                if level == "critical":
                    has_critical = True
                    logger.warning(log_msg)
                    if self.redact_critical:
                        cleaned = re.sub(pattern, "[REDACTED]", cleaned, flags=re.IGNORECASE)
                else:  # warning
                    logger.info(log_msg)

        # 补充：高熵随机串检测（与已知模式不重叠的片段）
        entropy_violations = self._check_entropy(cleaned)
        violations.extend(entropy_violations)

        is_safe = not (has_critical and self.block_critical)

        return OutputGuardResult(
            is_safe=is_safe,
            cleaned_text=cleaned,
            violations=violations,
        )

    def _check_entropy(self, text: str) -> list[str]:
        """检测高熵片段（可能是未匹配到的 Token/密钥）"""
        violations = []

        # 按常见分隔符 split，检测长片段高熵串
        tokens = re.split(r"[\s,;:\"'`|{}()\[\]<>]+", text)
        for token in tokens:
            # 只检测 20-100 字符的片段（太短不精确，太长不可能是 token）
            if 20 <= len(token) <= 100:
                entropy = self._shannon_entropy(token)
                if entropy > self.ENTROPY_THRESHOLD and self._looks_like_token(token):
                    violations.append(f"高熵随机串 (entropy={entropy:.1f})")
                    logger.warning(f"[OutputGuard] 高熵片段: len={len(token)}, entropy={entropy:.2f}")
                    break  # 一次只报一个

        return violations

    @staticmethod
    def _shannon_entropy(s: str) -> float:
        """计算 Shannon 熵（bit per character）"""
        if not s:
            return 0.0
        counts = Counter(s)
        total = len(s)
        entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
        return entropy

    @staticmethod
    def _looks_like_token(s: str) -> bool:
        """判断是否"看起来像"Token/密钥（字母数字混合，非自然语言）"""
        alnum = sum(1 for c in s if c.isalnum())
        return alnum / len(s) > 0.9 and any(c.isalpha() for c in s) and any(c.isdigit() for c in s)


# ============================================================
# 模块级单例
# ============================================================

_output_guard_instance: OutputGuard | None = None


def get_output_guard() -> OutputGuard:
    global _output_guard_instance
    if _output_guard_instance is None:
        _output_guard_instance = OutputGuard()
    return _output_guard_instance
