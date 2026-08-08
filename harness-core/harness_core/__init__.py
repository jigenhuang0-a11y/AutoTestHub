"""Agent Harness 中台内核。

这是新架构的唯一后端大脑，彻底替代 Django + LangGraph。
所有 Agent 行为都跑在自研 Loop Engine 上，所有模型调用都走统一底座。
"""

__version__ = "0.1.0"
