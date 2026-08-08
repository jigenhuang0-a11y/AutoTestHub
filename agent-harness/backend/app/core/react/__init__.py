"""
ReAct Agent Loop — Reasoning + Acting 多轮思考循环

让 LLM 自主决定"下一步做什么"：回答、调用工具、或请求澄清。

架构:
    ReActAgent
    ├── think_node:  LLM 推理 → 决定下一步 (content / tool_call / finish)
    ├── act_node:    执行工具 (通过 ToolGateway) → 获取观察结果
    └── observe_node: 整合结果 → 更新上下文 → 循环回 think 或结束

使用方式:
    from app.core.react import build_react_graph

    agent = build_react_graph(tools=[...], model="deepseek-chat")
    result = agent.invoke({"messages": [{"role": "user", "content": "生成登录测试用例"}]})
"""

from app.core.react.agent import ReActAgent
from app.core.react.graph import build_react_graph
from app.core.react.state import ReActState

__all__ = ["ReActAgent", "build_react_graph", "ReActState"]
