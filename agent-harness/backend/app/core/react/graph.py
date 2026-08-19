"""
ReAct LangGraph 图 — 将 ReActAgent 打包为 LangGraph StateGraph

这样可以在现有的 workflow.py 中作为子图嵌入：
    orchestrate_node → ReActGraph → verify_node
"""

import logging
from langgraph.graph import StateGraph, END

from app.core.react.state import ReActState, StepDecision, ThinkResult

logger = logging.getLogger(__name__)


def build_react_graph(react_agent) -> StateGraph:
    """
    构建 ReAct 推理图

    图结构:
        think ──tool_call──→ act ──→ observe ──→ think
          │                                              │
          └──content/finish──→ END                       └──max_iter──→ END

    Args:
        react_agent: ReActAgent 实例

    Returns:
        compiled StateGraph (支持 invoke/stream)
    """

    # ============================================================
    # 节点定义
    # ============================================================

    def think_node(state: dict) -> dict:
        """think: LLM 推理，决定下一步"""
        react_state = ReActState(
            messages=state.get("messages", []),
            max_iterations=state.get("max_iterations", 10),
            team_id=state.get("team_id", "default"),
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
            available_tools=state.get("available_tools", []),
            retrieved_memories=state.get("retrieved_memories", []),
            iteration=state.get("iteration", 0),
            trace_id=state.get("trace_id"),
        )

        think_result = react_agent.think(react_state)

        return {
            "decision": think_result.decision,
            "current_tool_calls": think_result.tool_calls,
            "reasoning": think_result.reasoning,
            "final_response": think_result.content,
            "messages": react_state.messages,
            "trace_id": react_state.trace_id,
        }

    def act_node(state: dict) -> dict:
        """act: 执行工具调用"""
        react_state = ReActState(
            messages=state.get("messages", []),
            team_id=state.get("team_id", "default"),
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
            current_tool_calls=state.get("current_tool_calls", []),
            trace_id=state.get("trace_id"),
        )

        react_state = react_agent.act(react_state)

        return {
            "messages": react_state.messages,
            "iteration": state.get("iteration", 0),
        }

    def observe_node(state: dict) -> dict:
        """observe: 观察结果，决定是否继续"""
        react_state = ReActState(
            messages=state.get("messages", []),
            max_iterations=state.get("max_iterations", 10),
            iteration=state.get("iteration", 0),
        )
        think_result = ThinkResult(
            decision=state.get("decision", StepDecision.FINISH),
            content=state.get("final_response", ""),
            tool_calls=state.get("current_tool_calls", []),
            reasoning=state.get("reasoning", ""),
        )

        react_state = react_agent.observe(react_state, think_result)

        return {
            "messages": react_state.messages,
            "iteration": react_state.iteration,
            "decision": react_state.decision,
            "final_response": react_state.final_response,
        }

    # ============================================================
    # 路由函数
    # ============================================================

    def route_after_think(state: dict) -> str:
        """think 后：调用工具？还是直接结束？"""
        decision = state.get("decision")
        if decision == StepDecision.TOOL_CALL:
            return "act"
        return "end"

    def route_after_observe(state: dict) -> str:
        """observe 后：继续思考？还是结束？"""
        decision = state.get("decision")
        iteration = state.get("iteration", 0)
        max_iter = state.get("max_iterations", 10)

        if decision == StepDecision.FINISH or iteration >= max_iter:
            return "end"
        return "think"

    # ============================================================
    # 构建图
    # ============================================================

    workflow = StateGraph(dict)

    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("observe", observe_node)

    workflow.set_entry_point("think")

    workflow.add_conditional_edges(
        "think",
        route_after_think,
        {"act": "act", "end": END},
    )

    workflow.add_edge("act", "observe")

    workflow.add_conditional_edges(
        "observe",
        route_after_observe,
        {"think": "think", "end": END},
    )

    return workflow.compile()
