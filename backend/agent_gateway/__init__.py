"""
Agent Gateway App — 统一 AI 入口

职责:
- 所有 AI 请求统一经过此 Gateway
- 请求校验、任务分发、SSE 流式推送
- 后端将业务请求转换为 LangGraph 工作流调用
"""
