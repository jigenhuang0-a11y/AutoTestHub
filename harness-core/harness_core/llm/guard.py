"""L1 模型底座 - 安全护栏。

两条护栏（P1 先做规则版，P2 可接模型判别）：
1. Prompt 注入检测：拦截常见的指令劫持模式。
2. 输出合规校验：拦截明显违规输出。

护栏失败不应抛异常中断业务，而是返回结构化结果交由调度层决策。
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GuardResult:
    passed: bool
    reason: str = ""


# Prompt 注入常见模式（规则版，可扩充）
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions", re.I),
    re.compile(r"disregard\s+(your|the)\s+(system|prior)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+\w+", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"<\s*(system|assistant|user)\s*>", re.I),
]

# 输出合规（占位规则，避免误伤正常用例内容）
_FORBIDDEN_OUTPUT = [
    re.compile(r"rm\s+-rf\s+/", re.I),
    re.compile(r"sudo\s+", re.I),
]


class Guardrail:
    def __init__(
        self,
        prompt_injection_check: bool = True,
        output_moderation: bool = True,
    ) -> None:
        self.prompt_injection_check = prompt_injection_check
        self.output_moderation = output_moderation

    def check_prompt(self, text: str) -> GuardResult:
        if not self.prompt_injection_check:
            return GuardResult(passed=True)
        for pat in _INJECTION_PATTERNS:
            if pat.search(text or ""):
                return GuardResult(
                    passed=False, reason=f"检测到 Prompt 注入模式: {pat.pattern}"
                )
        return GuardResult(passed=True)

    def check_output(self, text: str) -> GuardResult:
        if not self.output_moderation:
            return GuardResult(passed=True)
        for pat in _FORBIDDEN_OUTPUT:
            if pat.search(text or ""):
                return GuardResult(
                    passed=False, reason=f"输出命中合规拦截: {pat.pattern}"
                )
        return GuardResult(passed=True)
