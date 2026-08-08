"""
ReActAgent — 多轮思考-行动-观察循环

核心机制：
1. think: LLM 接收 messages + tools → 返回 text 或 tool_calls
2. act:   通过 ToolGateway 执行工具
3. observe: 将工具结果注入 messages
4. decide: 继续循环或结束
"""

import json
import time
import logging
from typing import Optional, Generator

from app.core.react.state import (
    ReActState, StepDecision, ToolCall, ThinkResult,
)
from app.core.react.prompts import REACT_SYSTEM_TEMPLATE
from app.core.robustness import call_llm_with_fallback, call_with_robustness

logger = logging.getLogger(__name__)


class ReActAgent:
    """
    ReAct 推理-行动 Agent

    封装 think → act → observe 循环逻辑。
    不直接依赖 LangGraph，以便可以在 LangGraph 节点或独立模式中使用。

    使用方式:
        agent = ReActAgent(
            router=llm_router,
            tool_gateway=gateway,
            max_iterations=10,
        )
        result = agent.run("生成 5 个登录页面的测试用例")
    """

    def __init__(
        self,
        router,          # LLMRouter 实例
        tool_gateway,    # LocalToolGateway 实例
        max_iterations: int = 10,
        team_id: str = "default",
    ):
        self.router = router
        self.gateway = tool_gateway
        self.max_iterations = max_iterations
        self.team_id = team_id

    # ============================================================
    # think — LLM 推理，决定下一步
    # ============================================================

    def think(self, state: ReActState) -> ThinkResult:
        """
        发送 messages + tools 给 LLM，获取推理结果。

        返回 ThinkResult:
        - decision=CONTENT: state.final_response 已设置
        - decision=TOOL_CALL: state.current_tool_calls 已填充
        - decision=FINISH: 循环结束
        """
        # 构建 tools 参数（OpenAI Function Calling 格式）
        tools = self._build_tools_param(state.available_tools)

        # 调用 LLM（支持 tool_choice）
        try:
            response = self._call_llm_with_tools(
                messages=state.messages,
                tools=tools,
            )
        except Exception as e:
            logger.error(f"[ReAct.think] LLM 调用失败: {e}")
            return ThinkResult(
                decision=StepDecision.CONTENT,
                content=f"推理失败: {e}",
            )

        # 解析 LLM 响应
        return self._parse_llm_response(response)

    def _build_tools_param(self, available_tools: list[dict]) -> list[dict]:
        """构建 OpenAI 兼容的 tools 参数"""
        if not available_tools:
            return []
        # available_tools 已经是 OpenAI FC 格式
        # 格式: [{"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}]
        return available_tools

    def _call_llm_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> dict:
        """
        通过 LLMRouter 调用 LLM 并传递 tools 参数（含降级保护）。

        Returns:
            {
                "content": "..." | None,
                "tool_calls": [{"id": "...", "function": {"name": "...", "arguments": "..."}}] | None,
            }
        """
        try:
            result = call_with_robustness(
                self.router.chat_with_tools,
                messages=messages,
                tools=tools,
                task_type="agent",
                temperature=0.3,
                circuit_name="react:agent",
                max_retries=1,
            )
            return result
        except Exception:
            # 最终降级：普通 chat（无 tools）
            try:
                content = call_llm_with_fallback(
                    self.router, messages, task_type="agent", fallback_model="deepseek-chat"
                )
            except Exception:
                content = self.router.chat(messages, task_type="agent")
            return {"content": content, "tool_calls": None}

    def _parse_llm_response(self, response: dict) -> ThinkResult:
        """解析 LLM 响应为结构化决策"""
        tool_calls_raw = response.get("tool_calls")
        content = response.get("content", "")

        if tool_calls_raw:
            # LLM 决定调用工具
            tool_calls = []
            for tc in tool_calls_raw:
                func = tc.get("function", {})
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    tool_name=func.get("name", ""),
                    arguments=args,
                ))
            return ThinkResult(
                decision=StepDecision.TOOL_CALL,
                tool_calls=tool_calls,
                reasoning=f"LLM 决定调用 {len(tool_calls)} 个工具",
            )

        if content:
            # LLM 直接回复（不需要调工具，或已完成思考）
            return ThinkResult(
                decision=StepDecision.CONTENT,
                content=content,
                reasoning="LLM 直接回复",
            )

        # 空响应 → 强制结束
        return ThinkResult(
            decision=StepDecision.FINISH,
            content="任务完成",
        )

    # ============================================================
    # act — 执行工具
    # ============================================================

    def act(self, state: ReActState) -> ReActState:
        """
        执行 state.current_tool_calls 中的所有工具调用。

        工具通过 ToolGateway 调用（含权限检查 + 审计）。
        """
        for tc in state.current_tool_calls:
            start = time.time()
            try:
                result = self.gateway.call_tool(
                    name=tc.tool_name,
                    arguments=tc.arguments,
                    team_id=state.team_id,
                    user_id=state.user_id,
                )
                tc.duration_ms = (time.time() - start) * 1000

                if result.get("isError"):
                    tc.error = result.get("content", [{}])[0].get("text", "未知错误")
                else:
                    tc.result = result
                    # 注入 tool message 到对话
                    content_text = self._result_to_text(result)
                    state.add_tool_result(
                        call_id=tc.tool_name,
                        tool_name=tc.tool_name,
                        result_text=content_text,
                    )
            except Exception as e:
                tc.error = str(e)
                tc.duration_ms = (time.time() - start) * 1000
                state.add_tool_result(
                    call_id=tc.tool_name,
                    tool_name=tc.tool_name,
                    result_text=f"执行失败: {e}",
                )

        state.current_tool_calls.clear()
        return state

    def _result_to_text(self, result: dict) -> str:
        """将工具结果转为可读文本"""
        try:
            content = result.get("content", [{}])
            if isinstance(content, list) and content:
                return content[0].get("text", str(result))
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception:
            return str(result)

    # ============================================================
    # observe — 观察工具结果，决定是否继续
    # ============================================================

    def observe(self, state: ReActState, think_result: ThinkResult) -> ReActState:
        """
        观察本轮执行结果，更新状态。

        检查:
        - 是否有工具调用失败 → 是否需要重试
        - 是否达到最大迭代 → 强制结束
        """
        state.iteration += 1
        state.decision = think_result.decision
        state.reasoning = think_result.reasoning

        if think_result.decision == StepDecision.CONTENT:
            state.final_response = think_result.content
            state.decision = StepDecision.FINISH

        if state.iteration >= state.max_iterations:
            logger.warning(f"[ReAct] 达到最大迭代次数 {state.max_iterations}")
            state.final_response = state.final_response or "已达到最大思考轮数，任务终止。"
            state.decision = StepDecision.FINISH

        return state

    # ============================================================
    # run — 主循环入口
    # ============================================================

    def run(
        self,
        task: str,
        context: dict = None,
        available_tools: list[dict] = None,
        user_id: int = None,
        task_id: str = None,
    ) -> ReActState:
        """
        执行完整的 ReAct 循环

        Args:
            task: 用户任务描述
            context: 已有上下文
            available_tools: OpenAI FC 格式的工具列表
            user_id: 用户 ID
            task_id: 任务 ID

        Returns:
            ReActState 包含完整执行过程
        """
        state = ReActState(
            max_iterations=self.max_iterations,
            team_id=self.team_id,
            user_id=user_id,
            task_id=task_id,
            available_tools=available_tools or [],
        )

        # 初始化消息
        if context:
            state.messages.append({
                "role": "system",
                "content": f"已有上下文: {json.dumps(context, ensure_ascii=False)}"
            })
        state.add_user_message(task)

        # 主循环
        while state.should_continue():
            logger.info(f"[ReAct] 迭代 {state.iteration + 1}/{self.max_iterations}")

            # think
            think_result = self.think(state)

            if think_result.decision == StepDecision.TOOL_CALL:
                # act
                state.current_tool_calls = think_result.tool_calls
                state = self.act(state)

                # observe → 决定继续或结束
                state = self.observe(state, think_result)
            else:
                # content 或 finish
                state = self.observe(state, think_result)
                break

        logger.info(f"[ReAct] 完成: {state.iteration} 轮, 最终决策={state.decision}")
        return state

    def run_stream(
        self,
        task: str,
        **kwargs,
    ) -> Generator[dict, None, None]:
        """
        流式执行 ReAct 循环（SSE 兼容）

        每步 yield: {"type": "think"|"act"|"observe"|"done", "data": ...}
        """
        state = self.run(task, **kwargs)

        # 回放完整执行过程
        for i in range(len(state.messages)):
            msg = state.messages[i]
            if msg["role"] == "user":
                yield {"type": "user", "data": msg["content"]}
            elif msg["role"] == "assistant":
                yield {"type": "think", "data": msg["content"]}
            elif msg["role"] == "tool":
                yield {"type": "act", "data": {"tool": msg["name"], "result": msg["content"]}}

        yield {"type": "done", "data": {
            "final_response": state.final_response,
            "iterations": state.iteration,
            "decision": state.decision.value if state.decision else "unknown",
        }}
