"""测试用例生成插件（P1 硬编码实现占位）。

P0 仅完成注册与接口骨架，实际 LLM 调用在 P1 接入统一模型底座后补齐。
"""
from __future__ import annotations

from harness_core.plugins import BasePlugin, PluginContext, PluginResult, register_plugin


@register_plugin
class TestcaseGenPlugin(BasePlugin):
    key = "testcase_gen"
    name = "AI 测试用例生成"
    sandbox_required = False

    async def execute(self, ctx: PluginContext, payload: dict) -> PluginResult:
        # TODO(P1): 调用统一模型底座生成用例，写入存储
        requirement = payload.get("requirement", "")
        if not requirement:
            return PluginResult(success=False, error="requirement 不能为空")
        return PluginResult(
            success=True,
            data={"requirement": requirement, "status": "placeholder"},
        )
