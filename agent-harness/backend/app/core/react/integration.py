"""
ReAct 集成入口 — 如何在现有 workflow.py 中使用 ReActAgent

这个文件展示接入点，不需要改 workflow.py 的核心结构。

集成方式 A — 嵌入 orchestrate_node（渐进式）:
    workflow.py 的 orchestrate_node 中，单个步骤如果标记了 react_step=True，
    则使用 ReActAgent 执行该步骤（而非旧的 execute_single_step）。

集成方式 B — 替换 plan → orchestrate → verify（全面重构）:
    plan_node → ReActGraph → verify_node
    其中 ReActGraph 替代 orchestrate_node 的全部逻辑。

推荐先做方式 A（风险低），验证后再切方式 B。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ReActIntegration:
    """
    ReAct 集成辅助类。

    提供快捷函数来创建和运行 ReActAgent，
    封装了 router + gateway + memory 的初始化。
    """

    def __init__(
        self,
        router=None,
        gateway=None,
        memory_manager=None,
        team_id: str = "default",
        max_iterations: int = 10,
    ):
        self.router = router
        self.gateway = gateway
        self.memory = memory_manager
        self.team_id = team_id
        self.max_iterations = max_iterations

    def execute_step_with_react(
        self,
        step: dict,
        state: dict,
    ) -> dict:
        """
        方式 A：用 ReAct 执行单个编排步骤。

        当 step 中 react=True 或 agent 在 REACT_CAPABLE 列表中时，
        用 ReActAgent 替代旧的 _execute_single_step()。

        Args:
            step: {"agent": "generator", "prompt": "...", "react": True}
            state: workflow state dict

        Returns:
            {"status": "success", "data": {...}, "react_trace": [...]}
        """
        from app.core.react.agent import ReActAgent
        from app.core.react.memory_bridge import ReActMemoryBridge

        # 初始化
        agent = ReActAgent(
            router=self.router,
            tool_gateway=self.gateway,
            max_iterations=self.max_iterations,
            team_id=self.team_id,
        )

        bridge = ReActMemoryBridge(memory=self.memory, gateway=self.gateway)

        # 获取可用工具
        available_tools = state.get("available_tools", [])
        if not available_tools and self.gateway:
            try:
                available_tools = self.gateway.list_tools(
                    team_id=self.team_id, format="openai"
                ).get("tools", [])
            except Exception:
                pass

        # 执行
        react_state = agent.run(
            task=step.get("prompt", ""),
            context=state.get("context"),
            available_tools=available_tools,
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
        )

        # 桥接记忆
        bridge.post_task(react_state)

        return {
            "status": "success",
            "data": {"response": react_state.final_response},
            "react_trace": {
                "iterations": react_state.iteration,
                "decision": react_state.decision.value if react_state.decision else "unknown",
                "messages": react_state.messages,
            },
        }

    def run_full_react_workflow(
        self,
        task: str,
        user_id: int = None,
        task_id: str = None,
        available_tools: list = None,
    ) -> dict:
        """
        方式 B：完整 ReAct 工作流（无需 plan/orchestrate/verify）。

        适用于简单到中等复杂度的任务：
        - "生成 5 个登录测试用例"
        - "分析这段代码的测试覆盖率"
        - "解释这个测试为什么失败"

        Args:
            task: 用户任务
            user_id: 用户 ID
            task_id: 任务 ID
            available_tools: 可用工具列表

        Returns:
            {"final_response": "...", "iterations": 3, "trace": [...]}
        """
        from app.core.react.agent import ReActAgent
        from app.core.react.memory_bridge import ReActMemoryBridge

        agent = ReActAgent(
            router=self.router,
            tool_gateway=self.gateway,
            max_iterations=self.max_iterations,
            team_id=self.team_id,
        )
        bridge = ReActMemoryBridge(memory=self.memory, gateway=self.gateway)

        # 获取工具
        tools = available_tools or []
        if not tools and self.gateway:
            try:
                tools = self.gateway.list_tools(
                    team_id=self.team_id, format="openai"
                ).get("tools", [])
            except Exception:
                pass

        # 开始任务
        if self.memory:
            self.memory.start_task(task_id or "unknown")

        # 执行
        react_state = agent.run(
            task=task,
            available_tools=tools,
            user_id=user_id,
            task_id=task_id,
        )

        # 记忆桥接
        bridge.post_task(react_state)

        return {
            "final_response": react_state.final_response,
            "iterations": react_state.iteration,
            "decision": react_state.decision.value if react_state.decision else "unknown",
            "trace": [
                {"role": m["role"], "content": m.get("content", "")[:200]}
                for m in react_state.messages
            ],
        }


# ============================================================
# 全局工厂函数
# ============================================================

_integration: Optional[ReActIntegration] = None


def get_react_integration(**kwargs) -> ReActIntegration:
    """
    获取全局 ReActIntegration 实例。

    首次调用时自动注入真实的 ToolGatewayClient + LLMRouter，
    确保 ReActAgent 能访问真实的 MCP 工具（而非 mock 数据）。

    Usage:
        # 方式 1：自动创建（推荐）
        react = get_react_integration()

        # 方式 2：传入自定义组件
        react = get_react_integration(
            gateway=my_gateway, router=my_router,
            team_id="team_a", max_iterations=5,
        )

        # 方式 3：仅更新 auth_token
        react = get_react_integration(auth_token="jwt_xxx")
    """
    global _integration

    auth_token = kwargs.pop("auth_token", None)

    if _integration is None:
        # 如果没有传入 gateway/router，自动创建真实实例
        if "gateway" not in kwargs or "router" not in kwargs:
            from app.core.gateway_factory import get_tool_gateway_client
            from app.core.router import get_llm_router

            kwargs.setdefault("gateway", get_tool_gateway_client(auth_token=auth_token))
            kwargs.setdefault("router", get_llm_router())

        _integration = ReActIntegration(**kwargs)
        logger.info("[ReActIntegration] 全局实例已初始化（含真实 gateway）")

    # 运行时刷新 auth_token
    if auth_token:
        from app.core.gateway_factory import get_tool_gateway_client
        get_tool_gateway_client(auth_token=auth_token)

    return _integration


def reset_react_integration():
    """重置全局 ReActIntegration（测试用）"""
    global _integration
    _integration = None
