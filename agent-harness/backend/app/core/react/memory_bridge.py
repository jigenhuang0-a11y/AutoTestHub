"""
ReAct ←→ Memory 桥接层

在 ReAct 循环中注入记忆：
    1. pre_think:    检索相关记忆 → 注入 system prompt
    2. post_observe: 工具结果 → 自动提取关键信息 → 存入长期记忆
    3. post_task:    任务结束 → 清理工作记忆
"""

import logging
from typing import Optional

from app.core.react.state import ReActState
from app.core.react.prompts import REACT_SYSTEM_TEMPLATE

logger = logging.getLogger(__name__)


class ReActMemoryBridge:
    """
    ReAct 循环与记忆系统的桥梁。

    使用方式:
        bridge = ReActMemoryBridge(memory_manager, gateway)
        
        # 在 ReAct 开始前
        state = bridge.pre_think(state)
        
        # 在每轮 observe 后
        state = bridge.post_observe(state)
        
        # 任务结束
        bridge.post_task(state)
    """

    def __init__(self, memory_manager, gateway=None):
        self.memory = memory_manager
        self.gateway = gateway  # ToolGateway 用于获取工具列表描述

    def pre_think(self, state: ReActState) -> ReActState:
        """
        ReAct 第 0 轮：注入记忆上下文。

        1. 从长期记忆检索相关内容
        2. 从短期记忆获取最近对话
        3. 构建含记忆的 system prompt
        """
        # 获取用户最新消息作为查询
        user_query = ""
        for msg in reversed(state.messages):
            if msg.get("role") == "user":
                user_query = msg.get("content", "")[:200]
                break

        # 检索记忆
        memory_context = self.memory.get_memory_context(query=user_query)
        state.retrieved_memories = (
            self.memory.retrieval.retrieve(user_query, team_id=state.team_id, limit=5)
            if user_query else []
        )

        # 如果 system prompt 尚未设置，注入含记忆的版本
        if not any(m.get("role") == "system" for m in state.messages):
            tools_desc = self._format_tools_description(state.available_tools)
            system_prompt = REACT_SYSTEM_TEMPLATE.format(
                max_iterations=state.max_iterations,
                tools_description=tools_desc,
                team_id=state.team_id,
                memory_context=memory_context,
            )
            state.messages.insert(0, {"role": "system", "content": system_prompt})

        logger.info(
            f"[ReAct.Bridge] pre_think: query='{user_query[:50]}...', "
            f"memories={len(state.retrieved_memories)}"
        )
        return state

    def post_observe(self, state: ReActState) -> ReActState:
        """
        工具结果观察后：自动提取关键信息。

        检查工具返回中是否有值得长期记忆的内容:
        - "testcase_search" → 用户查询偏好
        - "knowledge_search" → 用户关心的知识点
        - 错误信息 → 常见错误模式
        """
        # 取最近一次交互
        recent_messages = state.messages[-4:] if len(state.messages) >= 4 else state.messages

        # 自动提取（轻量级，不调用 LLM）
        try:
            self.memory.auto_extract_and_remember(
                messages=recent_messages,
                llm_fn=None,  # 暂不调用 LLM 提取，用简单规则
            )
        except Exception as e:
            logger.debug(f"[ReAct.Bridge] auto_extract 跳过: {e}")

        return state

    def post_task(self, state: ReActState) -> None:
        """任务结束：保存有价值信息，清理工作记忆"""
        try:
            # 保存最终结果到长期记忆
            if state.final_response:
                self.memory.remember(
                    content=f"[任务 {state.task_id}] 最终结果: {state.final_response[:300]}",
                    memory_type="lesson",
                    importance="low",
                    metadata={"task_id": state.task_id, "team_id": state.team_id},
                )
            # 关闭任务（清理工作记忆 + 自动保存）
            self.memory.close_task(save_to_long_term=True)
        except Exception as e:
            logger.warning(f"[ReAct.Bridge] post_task 异常: {e}")

    def _format_tools_description(self, available_tools: list[dict]) -> str:
        """格式化工具列表为可读描述"""
        if not available_tools:
            return "（无可用工具）"
        lines = []
        for tool in available_tools:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "无描述")
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)
