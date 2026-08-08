"""L2 能力支撑层 - 工具注册中心。

所有可调用的工具原语（函数型工具 / 沙箱型工具）在此统一注册。
插件在运行时通过名称获取工具，禁止插件自己 new 第三方客户端（红线 #1）。

P1 内存版注册表；P2 与 MySQL tool_registrations 表打通，支持动态注册。
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    # 实际执行函数（同步或 async）
    func: Callable[..., Any]
    sandbox_required: bool = False


ToolFunc = Callable[..., Awaitable[Any] | Any]

_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(
    name: str,
    description: str,
    sandbox_required: bool = False,
) -> Callable[[ToolFunc], ToolFunc]:
    def deco(func: ToolFunc) -> ToolFunc:
        _REGISTRY[name] = ToolSpec(
            name=name, description=description, func=func, sandbox_required=sandbox_required
        )
        return func

    return deco


def get_tool(name: str) -> ToolSpec | None:
    return _REGISTRY.get(name)


def list_tools() -> list[str]:
    return list(_REGISTRY.keys())


async def invoke_tool(name: str, **kwargs: Any) -> Any:
    """执行工具。P2 按 sandbox_required 路由到 OpenClaw 沙箱。"""
    spec = get_tool(name)
    if spec is None:
        raise KeyError(f"工具未注册: {name}")
    if spec.sandbox_required:
        from harness_core.sandbox import sandbox as _sandbox

        code = kwargs.get("code") or f"import json; print(json.dumps({kwargs!r}))"
        result = await _sandbox.run_code(code)
        if result.timed_out:
            raise RuntimeError(f"工具 {name} 沙箱执行超时")
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "sandbox": True,
        }
    if inspect.iscoroutinefunction(spec.func):
        return await spec.func(**kwargs)
    return spec.func(**kwargs)


# ---- 内置基础工具（演示用，证明工具中心可工作）----
@register_tool("echo", "回显输入，用于链路自检")
def _echo(text: str) -> str:
    return text


@register_tool("run_tests", "执行测试用例（占位，P2 接入真实测试框架）", sandbox_required=True)
def _run_tests(case_ids: list[str]) -> dict:
    # P1 沙箱未实装，本地兜底返回占位
    return {"executed": case_ids, "status": "sandbox-disabled-placeholder"}
