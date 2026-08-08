"""
Phase 2.6 冒烟测试 — 验证 ReAct 接入真实 ToolGateway
"""
import os
import sys
import json
import io

# Windows 下避免 GBK 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 确保能导入 app 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("SERVICE_TOKEN", "test-token")


def test_react_capable_agents():
    """验证 REACT_CAPABLE_AGENTS 常量存在且正确"""
    from app.core.workflow import REACT_CAPABLE_AGENTS

    assert "generator" in REACT_CAPABLE_AGENTS, "generator 应在 REACT_CAPABLE_AGENTS 中"
    assert "evaluator" in REACT_CAPABLE_AGENTS, "evaluator 应在 REACT_CAPABLE_AGENTS 中"
    assert "search" not in REACT_CAPABLE_AGENTS, "search 不应在 REACT_CAPABLE_AGENTS 中"
    print("✅ test_react_capable_agents passed")


def test_gateway_factory_import():
    """验证 Gateway 工厂能正常创建本地 LocalToolGateway（Django MCP 已移除）"""
    from app.core.gateway_factory import get_tool_gateway_client

    client = get_tool_gateway_client(auth_token="test-token")
    assert client is not None
    assert client.auth_token == "test-token"
    assert hasattr(client, "list_tools")
    assert hasattr(client, "call_tool")
    print("✅ test_gateway_factory_import passed")


def test_react_integration_singleton():
    """验证 ReActIntegration 单例模式"""
    from app.core.react.integration import get_react_integration, reset_react_integration

    # 重置状态
    reset_react_integration()

    # 第一次获取 — 应自动创建
    react1 = get_react_integration(auth_token="test-token")
    assert react1 is not None
    assert react1.gateway is not None  # 应有真实 gateway
    assert react1.router is not None   # 应有真实 router

    # 第二次获取 — 应返回同一实例
    react2 = get_react_integration()
    assert react1 is react2, "get_react_integration 应返回单例"

    print("✅ test_react_integration_singleton passed")


def test_react_state_structure():
    """验证 ReActState 数据结构符合预期"""
    from app.core.react.state import ReActState, StepDecision, ToolCall

    state = ReActState()
    state.final_response = "测试通过，生成 5 个用例"
    state.iteration = 3
    state.decision = StepDecision.FINISH
    state.add_tool_result("call_1", "search", "找到 3 条结果")

    assert state.final_response == "测试通过，生成 5 个用例"
    assert state.iteration == 3
    assert state.decision == StepDecision.FINISH
    assert len(state.messages) >= 1  # tool_result 添加了一条消息
    assert state.should_continue() == False  # FINISH 后不继续

    state_dict = state.to_dict()
    assert "final_response" in state_dict
    assert "iteration" in state_dict

    print("✅ test_react_state_structure passed")


def test_exec_react_step_in_workflow():
    """验证 workflow.py 中的 _exec_react_step 函数存在并可调用"""
    from app.core.workflow import _exec_react_step, REACT_CAPABLE_AGENTS

    assert callable(_exec_react_step), "_exec_react_step 应为可调用函数"
    assert isinstance(REACT_CAPABLE_AGENTS, frozenset)

    print("✅ test_exec_react_step_in_workflow passed")


def test_plan_prompt_has_react():
    """验证 PLAN_SYSTEM_PROMPT 包含 react 相关说明"""
    from app.core.workflow import PLAN_SYSTEM_PROMPT

    assert "react" in PLAN_SYSTEM_PROMPT, "PLAN_SYSTEM_PROMPT 应包含 react 说明"
    assert "ReAct" in PLAN_SYSTEM_PROMPT, "PLAN_SYSTEM_PROMPT 应提到 ReAct"

    print("✅ test_plan_prompt_has_react passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 2.6 冒烟测试 — ReAct 接入真实 ToolGateway")
    print("=" * 60)

    tests = [
        test_react_capable_agents,
        test_gateway_factory_import,
        test_react_integration_singleton,
        test_react_state_structure,
        test_exec_react_step_in_workflow,
        test_plan_prompt_has_react,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"结果: {passed}/{len(tests)} 通过, {failed}/{len(tests)} 失败")
    print("=" * 60)
