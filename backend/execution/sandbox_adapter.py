"""
Django 侧沙箱适配器

把原有的裸 subprocess.run() 替换为沙箱执行，不改动业务逻辑。

使用方式：
    改前：
        result = subprocess.run(cmd, timeout=600, ...)

    改后：
        from execution.sandbox_adapter import sandbox_run
        result = sandbox_run(cmd, timeout=600, max_memory_mb=1024)

沙箱不可用时自动回退到裸 subprocess，保证兼容性。
"""

import os
import sys
import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# 尝试导入编排服务的沙箱模块
_SANDBOX_AVAILABLE = False
_SandboxExecutor = None
_SandboxConfig = None
_SandboxResult = None
_SandboxStatus = None

try:
    _orchestration_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "agent-harness", "backend"
    )
    if _orchestration_path not in sys.path:
        sys.path.insert(0, _orchestration_path)

    from app.core.sandbox import (
        SandboxExecutor,
        SandboxConfig,
        SandboxResult,
        SandboxStatus,
    )
    _SANDBOX_AVAILABLE = True
    logger.info("[SandboxAdapter] 沙箱模块加载成功")
except ImportError as e:
    logger.warning(
        f"[SandboxAdapter] 沙箱模块不可用 (路径: {_orchestration_path if '_orchestration_path' in dir() else 'N/A'})，"
        f"将回退到裸 subprocess: {e}"
    )


@dataclass
class ExecutionResult:
    """统一的执行结果，兼容 subprocess.CompletedProcess 和 SandboxResult"""
    returncode: int
    stdout: str
    stderr: str
    success: bool
    killed_by_timeout: bool = False
    killed_by_memory: bool = False
    duration_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    error_message: str = ""


def sandbox_run(
    cmd: list[str],
    timeout: int = 300,
    max_memory_mb: int = 512,
    cwd: str = None,
    env: dict = None,
    use_sandbox: bool = True,
) -> ExecutionResult:
    """
    在沙箱中执行命令。

    Args:
        cmd: 命令行列表，如 ["python", "-m", "pytest", "test.py"]
        timeout: 超时秒数
        max_memory_mb: 最大内存 MB
        cwd: 工作目录（沙箱模式下会忽略，用临时目录）
        env: 环境变量
        use_sandbox: 是否使用沙箱，False 时走裸 subprocess

    Returns:
        ExecutionResult
    """
    if use_sandbox and _SANDBOX_AVAILABLE:
        return _run_with_sandbox(cmd, timeout, max_memory_mb, cwd, env)
    else:
        if use_sandbox and not _SANDBOX_AVAILABLE:
            logger.debug("[SandboxAdapter] 沙箱不可用，回退 subprocess")
        return _run_with_subprocess(cmd, timeout, cwd, env)


def _run_with_sandbox(
    cmd: list[str],
    timeout: int,
    max_memory_mb: int,
    cwd: str = None,
    env: dict = None,
) -> ExecutionResult:
    """沙箱模式执行"""
    config = SandboxConfig(
        timeout_seconds=timeout,
        max_memory_mb=max_memory_mb,
        cleanup_after=True,
    )
    executor = SandboxExecutor(config)
    result = executor.run_command(cmd, extra_env=env)

    return ExecutionResult(
        returncode=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        success=result.ok,
        killed_by_timeout=(result.status == SandboxStatus.TIMEOUT),
        killed_by_memory=(result.status == SandboxStatus.MEMORY_EXCEEDED),
        duration_seconds=result.duration_seconds,
        peak_memory_mb=result.peak_memory_mb,
        error_message=result.error_message,
    )


def _run_with_subprocess(
    cmd: list[str],
    timeout: int,
    cwd: str = None,
    env: dict = None,
) -> ExecutionResult:
    """裸 subprocess 回退模式"""
    import time as time_module
    start = time_module.time()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
        return ExecutionResult(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            success=(proc.returncode == 0),
            duration_seconds=time_module.time() - start,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            returncode=-1,
            stdout="",
            stderr="",
            success=False,
            killed_by_timeout=True,
            duration_seconds=time_module.time() - start,
            error_message=f"执行超时 ({timeout}s)",
        )
    except Exception as e:
        return ExecutionResult(
            returncode=-1,
            stdout="",
            stderr=str(e),
            success=False,
            duration_seconds=time_module.time() - start,
            error_message=str(e),
        )


def is_sandbox_available() -> bool:
    """检查沙箱模块是否可用"""
    return _SANDBOX_AVAILABLE
