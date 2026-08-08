"""
自主纠错 (Self-Healing) 模块

Phase 5.2: 智能错误分析与自动修复
"""

from .engine import (
    SelfHealingEngine,
    ErrorClassifier,
    FixStrategy,
    RetryWithBackoff,
    AIFixSyntax,
    AIDiagnose,
    ErrorCategory,
    Severity,
    ErrorAnalysis,
    HealingRecord,
    create_self_healing_engine,
)

__all__ = [
    "SelfHealingEngine",
    "ErrorClassifier",
    "FixStrategy",
    "RetryWithBackoff",
    "AIFixSyntax",
    "AIDiagnose",
    "ErrorCategory",
    "Severity",
    "ErrorAnalysis",
    "HealingRecord",
    "create_self_healing_engine",
]
