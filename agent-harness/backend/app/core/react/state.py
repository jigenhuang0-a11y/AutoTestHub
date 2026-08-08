"""
ReAct Agent 状态定义

一条思考-行动-观察循环的完整状态。
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class StepDecision(str, Enum):
    """每步推理后的决策"""
    CONTENT = "content"        # 直接回复用户（任务完成或需要澄清）
    TOOL_CALL = "tool_call"    # 需要调用工具获取信息
    FINISH = "finish"          # 任务完成，退出循环


@dataclass
class ToolCall:
    """单次工具调用记录"""
    tool_name: str
    arguments: dict
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class ThinkResult:
    """think_node 的输出"""
    decision: StepDecision
    content: str = ""                         # 给用户的回复文本
    tool_calls: list[ToolCall] = field(default_factory=list)  # 本轮需要调用的工具
    reasoning: str = ""                       # LLM 的推理过程


@dataclass
class ReActState:
    """
    ReAct 循环的状态（LangGraph StateGraph 的 State）

    流程: messages(累积) → think → tool_calls → act → observation
          → 合并回 messages → think → ... → FINISH
    """
    # === 核心对话 ===
    messages: list[dict] = field(default_factory=list)
    # 格式: [{"role": "system|user|assistant|tool", "content": "..."}]
    # tool 消息需额外字段: tool_call_id, name

    # === 本轮决策 ===
    decision: Optional[StepDecision] = None
    current_tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning: str = ""

    # === 循环控制 ===
    iteration: int = 0
    max_iterations: int = 10
    final_response: str = ""

    # === 上下文 ===
    team_id: str = "default"
    user_id: Optional[int] = None
    task_id: Optional[str] = None
    available_tools: list[dict] = field(default_factory=list)
    # available_tools: OpenAI Function Calling 格式的工具列表

    # === 记忆 ===
    retrieved_memories: list[dict] = field(default_factory=list)
    # 从长期记忆中检索到的相关上下文

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_result(self, call_id: str, tool_name: str, result_text: str):
        self.messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "name": tool_name,
            "content": result_text,
        })

    def should_continue(self) -> bool:
        """判断是否继续循环"""
        if self.iteration >= self.max_iterations:
            return False
        if self.decision == StepDecision.FINISH:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "messages": self.messages,
            "decision": self.decision.value if self.decision else None,
            "iteration": self.iteration,
            "final_response": self.final_response,
            "team_id": self.team_id,
        }
