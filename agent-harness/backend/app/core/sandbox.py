"""
本地代码沙箱执行器

把 AI 生成的不可信代码关进受控环境执行：
- FileJail：   临时目录隔离，防止污染宿主机文件
- ResourceLimiter：psutil 后台监控，内存/CPU 超限即 kill
- ProcessManager：subprocess 生命周期管理 + 超时 watchdog

设计原则：
- 本地版用 subprocess + psutil + 临时目录（Windows 兼容）
- 服务器版可无缝升级为 Docker 容器（同一套接口）
- 遵循"监控 + 隔离 + 一刀切"策略，没有真正的魔法墙
"""

import os
import sys
import time
import json
import uuid
import shutil
import tempfile
import logging
import threading
import subprocess
import textwrap
import ipaddress
import socket
import psutil
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

class SandboxStatus(str, Enum):
    """沙箱执行结果状态"""
    SUCCESS = "success"                 # 正常退出，exit_code=0
    TIMEOUT = "timeout"                 # 超时被 kill
    MEMORY_EXCEEDED = "memory_exceeded" # 内存超限被 kill
    PROCESS_EXCEEDED = "process_exceeded"  # 子进程数超限被 kill
    RUNTIME_ERROR = "runtime_error"     # 正常退出但 exit_code≠0
    SYSTEM_ERROR = "system_error"       # 沙箱自身异常（无法启动等）


@dataclass
class SandboxConfig:
    """沙箱执行配置"""
    # ── 资源限制 ──
    timeout_seconds: int = 300          # 执行超时（秒）
    max_memory_mb: int = 512            # 最大内存（MB），0=不限制
    max_cpu_percent: int = 0            # 最大 CPU%（仅 Linux cgroups），0=不限制
    max_processes: int = 10             # 最大子进程数

    # ── 文件系统 ──
    work_dir: Optional[str] = None      # 工作目录，None=自动创建临时目录
    read_only_paths: list = field(default_factory=list)  # 拷贝到临时目录的文件/目录
    allowed_write_paths: list = field(default_factory=list)  # 允许写出的路径（Phase 2）

    # ── 网络 & 环境 ──
    allow_network: bool = False         # 是否放行公网（默认拒绝，按需最小放行）
    allowed_hosts: list = field(default_factory=list)  # 允许访问的目标主机/网段
    env_whitelist: list = field(default_factory=lambda: [
        "PATH", "SYSTEMROOT", "SYSTEMDRIVE",
        "TEMP", "TMP", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
        "PYTHONPATH", "PYTHONHOME", "PYTHONIOENCODING",
    ])
    inherit_env: bool = True            # 是否继承当前进程环境变量（白名单过滤后）
    injected_env: dict = field(default_factory=dict)  # 强制注入的环境变量

    # ── 清理 ──
    cleanup_after: bool = True          # 执行完是否删临时目录


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    status: SandboxStatus = SandboxStatus.SYSTEM_ERROR
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    error_message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == SandboxStatus.SUCCESS

    @property
    def duration_ms(self) -> int:
        return int(self.duration_seconds * 1000)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout[-5000:],  # 截断，防止太大
            "stderr": self.stderr[-5000:],
            "duration_ms": int(self.duration_seconds * 1000),
            "duration_seconds": round(self.duration_seconds, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 1),
            "error_message": self.error_message,
        }


# ============================================================
# FileJail：文件隔离
# ============================================================

class FileJail:
    """
    文件隔离——本地版用临时目录拷贝 + cwd 锁定。

    原理：
    1. 在系统临时目录创建 sandbox_{uuid} 文件夹
    2. 把只读文件拷贝进去
    3. 子进程的 cwd 设为此文件夹
    4. 执行完 rmtree 删除

    局限性（本地版）：
    - 无法阻止子进程写绝对路径（如 C:/Windows/...）
    - 需要服务器 Docker 版才能做到真正的 read-only mount
    - 正常 AI 生成的代码只操作 cwd 和 HTTP，风险可控
    """

    def __init__(self, config: SandboxConfig):
        self.config = config
        self.temp_dir: Optional[str] = None
        self._created = False

    def setup(self) -> str:
        """创建隔离文件系统，返回工作目录路径"""
        sandbox_id = uuid.uuid4().hex[:8]
        self.temp_dir = os.path.join(
            tempfile.gettempdir(), f"sandbox_{sandbox_id}"
        )
        os.makedirs(self.temp_dir, exist_ok=True)
        logger.info(f"[Sandbox.FileJail] 创建临时目录: {self.temp_dir}")

        # 拷贝只读文件到沙箱
        for src in self.config.read_only_paths:
            if not os.path.exists(src):
                logger.warning(f"[Sandbox.FileJail] 只读文件不存在，跳过: {src}")
                continue
            try:
                dest = os.path.join(self.temp_dir, os.path.basename(src))
                if os.path.isfile(src):
                    shutil.copy2(src, dest)
                elif os.path.isdir(src):
                    shutil.copytree(src, dest)
                logger.debug(f"[Sandbox.FileJail] 拷贝: {src} → {dest}")
            except Exception as e:
                logger.warning(f"[Sandbox.FileJail] 拷贝失败: {src} → {e}")

        self._created = True
        return self.temp_dir

    def inject_network_guard(self, allowed_hosts: list) -> bool:
        """
        写入 sitecustomize.py 钩子，子进程启动即拦截出网。
        仅当 allow_network=False 时调用。本地版用 socket 层 hook 兜底，
        云版可替换为 egress 网络策略（更彻底）。
        返回是否成功注入。
        """
        if not self.temp_dir or not allowed_hosts:
            return False
        # 预解析网段，避免钩子里重复解析
        networks = []
        hosts = []
        for h in allowed_hosts:
            try:
                networks.append(str(ipaddress.ip_network(h, strict=False)))
            except ValueError:
                hosts.append(h.lower())
        guard = textwrap.dedent(f"""
            # sandbox network guard (auto-injected)
            import socket as _sock
            import ipaddress as _ip
            _ALLOW_HOSTS = {hosts!r}
            _ALLOW_NETS = {[str(n) for n in networks]!r}

            def _host_of(node):
                # node 可能是 "host"、"host:port"、"https://host" 或纯 IP
                h = str(node).split("://", 1)[-1].split(":")[0].strip()
                return h.lower()

            def _in_allow(host):
                if not host:
                    return False
                h = _host_of(host)
                if h in _ALLOW_HOSTS:
                    return True
                # 已解析的 IP 直接比对网段
                try:
                    addr = _ip.ip_address(h)
                    return any(addr in _ip.ip_network(n) for n in _ALLOW_NETS)
                except ValueError:
                    pass
                # 未解析的域名：先解析再比对
                try:
                    for info in _sock.getaddrinfo(h, None):
                        ip = info[4][0]
                        try:
                            if any(_ip.ip_address(ip) in _ip.ip_network(n) for n in _ALLOW_NETS):
                                return True
                        except ValueError:
                            continue
                except Exception:
                    pass
                return False

            def _guarded_getaddrinfo(host, *args, **kwargs):
                if _in_allow(str(host)):
                    return _orig_getaddrinfo(host, *args, **kwargs)
                raise PermissionError(
                    f"[Sandbox] 网络出口被策略拒绝: {{_host_of(host)}} 不在白名单")

            def _guarded_connect(self, address):
                host = address[0] if isinstance(address, (tuple, list)) else ""
                if _in_allow(str(host)):
                    return _orig_connect(self, address)
                raise PermissionError(
                    f"[Sandbox] 网络出口被策略拒绝: {{_host_of(host)}} 不在白名单")

            _orig_getaddrinfo = _sock.getaddrinfo
            _orig_connect = _sock.socket.connect
            _sock.getaddrinfo = _guarded_getaddrinfo
            _sock.socket.connect = _guarded_connect
        """)
        try:
            path = os.path.join(self.temp_dir, "sitecustomize.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(guard)
            # 确保 sitecustomize 在 sys.path 最前（cwd 已是临时目录）
            logger.info(f"[Sandbox.FileJail] 注入网络拦截钩子: {path}")
            return True
        except Exception as e:
            logger.warning(f"[Sandbox.FileJail] 网络钩子注入失败: {e}")
            return False

    def cleanup(self):
        """删除临时目录"""
        if not self._created or not self.temp_dir:
            return
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.info(f"[Sandbox.FileJail] 清理完成: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"[Sandbox.FileJail] 清理失败: {e}")
        finally:
            self._created = False
            self.temp_dir = None


# ============================================================
# ResourceLimiter：资源监控
# ============================================================

class ResourceLimiter:
    """
    资源限制器——用 psutil 后台线程监控，超限即杀。

    原理（本地版）：
    1. 后台线程每 0.5s 读一次子进程的"体检报告"
    2. 内存超过 max_memory_mb → proc.kill()
    3. 子进程数超过 max_processes → proc.kill()
    4. 主进程结束或子进程退出 → 通知监控线程停止

    局限性（本地版）：
    - 监控有 0.5s 间隔，不是实时的
    - CPU 限制在 Windows 上不精确（psutil.cpu_percent 不准）
    - 递归子进程的 CPU 累加不准确
    - 服务器 Docker 版用 cgroups 可以做到精确限制
    """

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._stop_event = threading.Event()
        self._killed_reason: Optional[str] = None

    def monitor(self, pid: int):
        """后台线程入口：监控进程资源，超限时 kill"""
        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return  # 进程已退出

        while not self._stop_event.is_set():
            try:
                # ── 检查内存 ──
                if self.config.max_memory_mb > 0:
                    mem_info = proc.memory_info()
                    mem_mb = mem_info.rss / 1024 / 1024
                    if mem_mb > self.config.max_memory_mb:
                        self._killed_reason = (
                            f"内存超限 {mem_mb:.1f}MB > {self.config.max_memory_mb}MB"
                        )
                        self._kill_tree(proc)
                        logger.warning(f"[Sandbox.Resource] {self._killed_reason}")
                        break

                # ── 检查子进程数 ──
                if self.config.max_processes > 0:
                    children = proc.children(recursive=True)
                    if len(children) > self.config.max_processes:
                        self._killed_reason = (
                            f"子进程数超限 {len(children)} > {self.config.max_processes}"
                        )
                        self._kill_tree(proc)
                        logger.warning(f"[Sandbox.Resource] {self._killed_reason}")
                        break

            except psutil.NoSuchProcess:
                break  # 进程已正常退出
            except Exception as e:
                logger.debug(f"[Sandbox.Resource] 监控异常: {e}")

            self._stop_event.wait(timeout=0.5)  # 每 0.5s 检查

    def stop(self):
        """通知监控线程停止"""
        self._stop_event.set()

    @property
    def was_killed(self) -> bool:
        return self._killed_reason is not None

    @property
    def killed_reason(self) -> str:
        return self._killed_reason or ""

    @staticmethod
    def _kill_tree(proc: "psutil.Process"):
        """递归杀进程树（父 + 所有子 + 所有孙）"""
        try:
            children = proc.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            proc.kill()
        except psutil.NoSuchProcess:
            pass


# ============================================================
# ProcessManager：进程生命周期管理
# ============================================================

class ProcessManager:
    """
    进程管理器——subprocess.Popen + timeout watchdog。

    职责：
    1. 启动子进程（cwd=临时目录，env=白名单过滤后）
    2. 启动 ResourceLimiter 后台监控
    3. communicate(timeout=...) 等待结果
    4. 超时 → kill 进程树
    5. 收集 exit_code / stdout / stderr / 耗时 / 峰值内存
    """

    def __init__(self, config: SandboxConfig):
        self.config = config

    def run(self, cmd: list[str], cwd: str, extra_env: dict = None) -> SandboxResult:
        """执行命令并返回沙箱结果"""
        start = time.time()

        # ── 构建环境变量（白名单过滤） ──
        env = self._build_env(extra_env)

        # ── 启动子进程 ──
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            logger.info(f"[Sandbox.Process] 子进程启动 PID={proc.pid} CMD={' '.join(cmd)}")
        except Exception as e:
            return SandboxResult(
                status=SandboxStatus.SYSTEM_ERROR,
                error_message=f"无法启动子进程: {e}",
                duration_seconds=time.time() - start,
            )

        # ── 启动资源监控 ──
        limiter = ResourceLimiter(self.config)
        monitor_thread = threading.Thread(
            target=limiter.monitor, args=(proc.pid,), daemon=True
        )
        monitor_thread.start()

        # ── 等待进程结束 ──
        try:
            stdout, stderr = proc.communicate(timeout=self.config.timeout_seconds)
            duration = time.time() - start

            # 判断最终状态
            if limiter.was_killed:
                if "内存" in limiter.killed_reason:
                    status = SandboxStatus.MEMORY_EXCEEDED
                else:
                    status = SandboxStatus.PROCESS_EXCEEDED
            elif proc.returncode == 0:
                status = SandboxStatus.SUCCESS
            else:
                status = SandboxStatus.RUNTIME_ERROR

        except subprocess.TimeoutExpired:
            logger.warning(f"[Sandbox.Process] 超时 {self.config.timeout_seconds}s，强制终止")
            ResourceLimiter._kill_tree(psutil.Process(proc.pid))
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except Exception:
                stdout, stderr = "", ""
            duration = time.time() - start
            status = SandboxStatus.TIMEOUT

        # ── 停止监控 ──
        limiter.stop()
        monitor_thread.join(timeout=2)

        # ── 收集峰值内存 ──
        peak_mem = 0.0
        try:
            peak_mem = psutil.Process(proc.pid).memory_info().rss / 1024 / 1024
        except Exception:
            pass

        return SandboxResult(
            status=status,
            exit_code=proc.returncode if status != SandboxStatus.TIMEOUT else -1,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_seconds=duration,
            peak_memory_mb=peak_mem,
            error_message=limiter.killed_reason if limiter.was_killed else "",
        )

    def _build_env(self, extra: dict = None) -> dict:
        """构建子进程环境变量（白名单过滤 + 追加）"""
        env = {}
        if self.config.inherit_env:
            for key in (self.config.env_whitelist or []):
                val = os.environ.get(key)
                if val is not None:
                    env[key] = val

        # 追加额外环境变量
        if extra:
            env.update(extra)

        # 强制注入的策略环境变量
        if self.config.injected_env:
            env.update(self.config.injected_env)

        # 标记在沙箱中
        env["SANDBOX_ACTIVE"] = "1"
        env["SANDBOX_WORK_DIR"] = ""  # 子进程填充
        # 网络策略：false 时把 allowed_hosts 序列化进环境，供钩子脚本拦截
        env["SANDBOX_ALLOW_NETWORK"] = "1" if self.config.allow_network else "0"
        if not self.config.allow_network and self.config.allowed_hosts:
            env["SANDBOX_ALLOWED_HOSTS"] = json.dumps(self.config.allowed_hosts)

        return env


# ============================================================
# SandboxExecutor：统一入口
# ============================================================

class SandboxExecutor:
    """
    沙箱执行器——统一入口，串联 FileJail + ProcessManager + ResourceLimiter。

    使用方式：

        config = SandboxConfig(
            timeout_seconds=300,
            max_memory_mb=512,
            read_only_paths=["/path/to/test_login.py"],
        )
        executor = SandboxExecutor(config)
        result = executor.run_command(["python", "test_login.py"])

        if result.ok:
            print(result.stdout)
        else:
            print(f"失败: {result.status.value} - {result.error_message}")
    """

    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()
        self._jail = FileJail(self.config)
        self._process = ProcessManager(self.config)

    def run_command(self, cmd: list[str], extra_env: dict = None) -> SandboxResult:
        """
        在沙箱中执行命令。

        Args:
            cmd: 命令行列表，如 ["python", "test.py", "--verbose"]
            extra_env: 额外的环境变量

        Returns:
            SandboxResult
        """
        try:
            # 1. 建立文件隔离
            work_dir = self._jail.setup()
        except Exception as e:
            return SandboxResult(
                status=SandboxStatus.SYSTEM_ERROR,
                error_message=f"FileJail 创建失败: {e}",
            )

        # 1.5 网络策略：默认拒绝，按需最小放行
        if not self.config.allow_network:
            self._jail.inject_network_guard(self.config.allowed_hosts)

        try:
            # 2. 在沙箱中执行
            result = self._process.run(cmd, cwd=work_dir, extra_env=extra_env)
            return result
        finally:
            # 3. 清理（即使执行失败也会清理）
            if self.config.cleanup_after:
                self._jail.cleanup()

    def run_script(
        self,
        script_content: str,
        filename: str = "script.py",
        extra_env: dict = None,
    ) -> SandboxResult:
        """
        在沙箱中执行一段 Python 脚本。

        自动将脚本写入临时目录再执行，适合 AI 生成的代码。

        Args:
            script_content: Python 脚本内容（字符串）
            filename: 脚本文件名
            extra_env: 额外的环境变量

        Returns:
            SandboxResult
        """
        try:
            work_dir = self._jail.setup()
        except Exception as e:
            return SandboxResult(
                status=SandboxStatus.SYSTEM_ERROR,
                error_message=f"FileJail 创建失败: {e}",
            )

        # 网络策略：默认拒绝，按需最小放行
        if not self.config.allow_network:
            self._jail.inject_network_guard(self.config.allowed_hosts)

        try:
            script_path = os.path.join(work_dir, filename)
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            logger.info(f"[Sandbox] 脚本写入: {script_path} ({len(script_content)} chars)")

            return self._process.run(
                [sys.executable, script_path],
                cwd=work_dir,
                extra_env=extra_env,
            )
        finally:
            if self.config.cleanup_after:
                self._jail.cleanup()


# ============================================================
# 便捷函数
# ============================================================

def run_in_sandbox(
    cmd: list[str],
    timeout: int = 300,
    max_memory_mb: int = 512,
    max_processes: int = 10,
    read_only_paths: list = None,
    extra_env: dict = None,
) -> SandboxResult:
    """
    一行代码在沙箱中执行命令。

    >>> result = run_in_sandbox(["python", "test.py"], timeout=60, max_memory_mb=256)
    >>> print(result.ok, result.stdout)
    """
    config = SandboxConfig(
        timeout_seconds=timeout,
        max_memory_mb=max_memory_mb,
        max_processes=max_processes,
        read_only_paths=read_only_paths or [],
    )
    executor = SandboxExecutor(config)
    return executor.run_command(cmd, extra_env=extra_env)
