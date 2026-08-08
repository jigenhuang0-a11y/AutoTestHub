"""L2 能力支撑层 - OpenClaw 沙箱（P2 实装）。

基于 Docker Python SDK 提供隔离执行环境：
- 每个工具/代码在独立容器运行，限制 CPU / 内存 / 超时
- 与宿主机网络隔离，防止恶意代码影响中台
- P1 沙箱未实装时，gateway 配置 sandbox_enabled=False，走本地兜底

设计要点（商业化卖点）：
- 沙箱是能力支撑层的一等公民，插件声明 sandbox_required 即自动进沙箱
- 资源配额从 config 读取，可随租户等级动态调整（P3）
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from harness_core.config import settings
from harness_core.logging import logger


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


class DockerSandbox:
    """Docker 隔离执行器（OpenClaw 沙箱）。

    未安装 docker / 未启用时，自动降级为本地执行（带超时保护）。
    """

    def __init__(self) -> None:
        self.enabled = settings.sandbox_enabled
        self._docker = None
        if self.enabled:
            try:
                import docker

                self._docker = docker.from_env()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[sandbox] Docker 不可用，降级本地执行: {e}")
                self.enabled = False

    async def run_code(self, code: str, *, image: str | None = None, timeout: int | None = None) -> SandboxResult:
        timeout = timeout or settings.sandbox_timeout_seconds
        if not self.enabled:
            return await self._run_local(code, timeout)
        return await self._run_docker(code, image or settings.sandbox_docker_image, timeout)

    async def _run_docker(self, code: str, image: str, timeout: int) -> SandboxResult:
        def _exec() -> SandboxResult:
            container = self._docker.containers.run(
                image,
                command=["python", "-c", code],
                mem_limit=f"{settings.sandbox_memory_mb}m",
                nano_cpus=int(settings.sandbox_cpu_limit * 1e9),
                network_disabled=True,
                detach=False,
                remove=True,
            )
            return SandboxResult(stdout=str(container), stderr="", exit_code=0)

        try:
            return await asyncio.wait_for(asyncio.to_thread(_exec), timeout=timeout)
        except asyncio.TimeoutError:
            return SandboxResult(stdout="", stderr="", exit_code=-1, timed_out=True)

    async def _run_local(self, code: str, timeout: int) -> SandboxResult:
        """本地兜底执行（仅演示 / 开发用，生产必须 Docker）。"""
        proc = await asyncio.create_subprocess_exec(
            "python", "-c", code,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return SandboxResult(stdout="", stderr="", exit_code=-1, timed_out=True)
        return SandboxResult(
            stdout=out.decode("utf-8", "ignore"),
            stderr=err.decode("utf-8", "ignore"),
            exit_code=proc.returncode or 0,
        )


# 全局单例
sandbox = DockerSandbox()
