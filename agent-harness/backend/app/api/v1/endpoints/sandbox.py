"""
沙箱管控接口

核心流程：代码提交 → 安全检查 → 沙箱隔离执行 → 审计记录 → 销毁沙箱

安全链路：
1. CodeSafetyChecker 扫描代码中的危险模式（eval/exec/os.system等）
2. safe/warning 级别放行进入沙箱，dangerous 级别直接拒绝
3. 沙箱执行结果记录到 AuditStore（审计持久化）
4. 临时沙箱执行完毕自动销毁

Phase 2.3：沙箱实例持久化到 SQLite，替换 MOCK_SANDBOXES 内存数据。
"""
import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.sandbox import SandboxConfig, SandboxExecutor
from app.core.code_safety import get_safety_checker, SafetyRejected
from app.core.audit_store import get_audit_store
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)
from app.api.v1.endpoints.auth import require_non_viewer

router = APIRouter()

SANDBOX_TYPES = ["python", "node", "browser"]
STATUSES = ["running", "idle", "terminated"]


class SandboxInstanceManager:
    """
    进程内沙箱实例管理器：维护常驻 SandboxExecutor 实例，
    让「沙箱管控」页面真实对接运行中的沙箱（而非空表占位）。
    - create: 实例化 SandboxExecutor 并探活（执行探针脚本）
    - list:   实时回写存活状态与资源占用
    - stop:   停止并清理常驻实例
    """

    def __init__(self):
        self._instances: dict[str, "SandboxExecutor"] = {}
        self._created_at: dict[str, float] = {}

    def create(self, sbx_id: str, sbx_type: str, memory_mb: int) -> bool:
        """拉起常驻沙箱实例并探活。"""
        try:
            config = SandboxConfig(
                timeout_seconds=1800,
                max_memory_mb=memory_mb,
                cleanup_after=False,  # 常驻，由 manager 显式停止
            )
            executor = SandboxExecutor(config)
            probe_script = "print('sandbox_probe_ok')" if sbx_type == "python" else "console.log('sandbox_probe_ok')"
            probe = (
                executor.run_script(probe_script)
                if sbx_type == "python"
                else executor.run_command(["node", "-e", probe_script], cwd=executor._jail.setup())
            )
            if not probe.ok:
                logger.warning(f"[SandboxManager] 探活失败 {sbx_id}: {probe.error_message}")
                return False
            self._instances[sbx_id] = executor
            self._created_at[sbx_id] = __import__("time").time()
            return True
        except Exception as e:
            logger.warning(f"[SandboxManager] 创建失败 {sbx_id}: {e}")
            return False

    def is_alive(self, sbx_id: str) -> bool:
        return sbx_id in self._instances

    def stop(self, sbx_id: str) -> None:
        inst = self._instances.pop(sbx_id, None)
        if inst is not None:
            try:
                if hasattr(inst, "_jail"):
                    inst._jail.cleanup()
            except Exception:
                pass
        self._created_at.pop(sbx_id, None)

    def uptime(self, sbx_id: str) -> int:
        ts = self._created_at.get(sbx_id)
        if ts is None:
            return 0
        return int(__import__("time").time() - ts)


_manager = SandboxInstanceManager()


class SandboxItem(BaseModel):
    id: str
    name: str
    type: str
    status: str
    memory_mb: int
    memory_used_mb: int
    cpu_percent: int
    uptime_seconds: int
    host: str
    created_at: str


class SandboxSummary(BaseModel):
    total: int
    running: int
    idle: int
    terminated: int


class SandboxList(BaseModel):
    items: list[SandboxItem]
    summary: SandboxSummary


class SandboxCreate(BaseModel):
    type: str
    memory_mb: int
    name: Optional[str] = None


class SandboxExecuteRequest(BaseModel):
    code: str
    timeout: Optional[int] = 300
    repo_url: Optional[str] = None      # Git 仓库地址
    branch: Optional[str] = "main"       # 分支


class SandboxExecuteResult(BaseModel):
    ok: bool
    status: str
    stdout: str = ""
    stderr: str = ""
    error_message: str = ""
    duration_ms: int = 0


class SafetyCheckedExecuteRequest(BaseModel):
    """带安全检查的执行请求（工作流用）"""
    code: str
    language: str = "python"           # python / node
    timeout: int = 300
    task_id: str = ""
    user_id: str = ""
    team_id: str = "default"
    repo_url: Optional[str] = None      # Git 仓库地址
    branch: Optional[str] = "main"       # 分支


class SafetyCheckedExecuteResponse(BaseModel):
    """安全检查 + 沙箱执行的完整响应"""
    ok: bool
    task_id: str
    # 安全检查结果
    safety_checked: bool
    safety_passed: bool
    safety_level: str = ""            # safe / warning / dangerous
    safety_summary: str = ""
    safety_issues: list = []
    # 沙箱执行结果（仅 safety_passed=true 时有值）
    sandbox_status: str = ""
    sandbox_stdout: str = ""
    sandbox_stderr: str = ""
    sandbox_duration_ms: int = 0
    error_message: str = ""
    # 审计记录 ID
    audit_id: int = 0


def _build_summary(items: list[dict]) -> SandboxSummary:
    """从沙箱列表构建统计摘要"""
    summary = {"total": 0, "running": 0, "idle": 0, "terminated": 0}
    for s in items:
        summary["total"] += 1
        st = s.get("status", "")
        if st in summary:
            summary[st] += 1
    return SandboxSummary(**summary)


def _clone_repo(repo_url: str, branch: str = "main"):
    """
    将 Git 仓库克隆到临时目录，返回 path 和 cleanup 函数。

    如果 git 不可用或克隆失败则抛异常，由上层捕获返回友好错误。
    """
    clone_dir = tempfile.mkdtemp(prefix="sbx_repo_")
    logger.info(f"[Sandbox.Git] 正在克隆 {repo_url}@{branch} → {clone_dir}")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, repo_url, clone_dir],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        shutil.rmtree(clone_dir, ignore_errors=True)
        stderr = (e.stderr or "").strip()
        raise RuntimeError(f"git clone 失败: {stderr}" if stderr else f"git clone 返回码 {e.returncode}") from e
    except FileNotFoundError:
        shutil.rmtree(clone_dir, ignore_errors=True)
        raise RuntimeError("系统未安装 git，无法克隆仓库。请在宿主机上安装 git 后重试。")
    except subprocess.TimeoutExpired:
        shutil.rmtree(clone_dir, ignore_errors=True)
        raise RuntimeError("git clone 超时（120s），请检查仓库地址或网络。")

    logger.info(f"[Sandbox.Git] 克隆完成: {clone_dir}")
    return clone_dir


# ──────────────── 沙箱实例管理（持久化） ────────────────

@router.get("/", response_model=SandboxList)
async def list_sandboxes(
    type: Optional[str] = Query(None, description="按类型过滤"),
):
    """获取沙箱实例列表（实时回写运行中实例的状态/资源）。"""
    store = get_task_store()
    items = store.list_sandboxes()
    if type:
        items = [s for s in items if s.get("type") == type]
    # 实时同步进程内常驻实例状态
    for s in items:
        sbx_id = s.get("id") or s.get("sbx_id")
        if _manager.is_alive(sbx_id):
            s["status"] = "running"
            s["uptime_seconds"] = _manager.uptime(sbx_id)
        elif s.get("status") not in ("terminated",):
            s["status"] = "idle"
    return SandboxList(items=items, summary=_build_summary(items))


@router.post("/")
async def create_sandbox(payload: SandboxCreate, user: dict = Depends(require_non_viewer)):
    """创建沙箱实例（真实拉起并探活）。"""
    sb_type = payload.type if payload.type in SANDBOX_TYPES else "python"
    memory_mb = max(256, min(payload.memory_mb or 512, 4096))
    name = payload.name or f"sbx-{sb_type}-{uuid.uuid4().hex[:4]}"

    store = get_task_store()
    record = store.create_sandbox(name=name, sbx_type=sb_type, memory_mb=memory_mb)
    sbx_id = record.sbx_id

    # 真实拉起沙箱实例
    ok = _manager.create(sbx_id, sb_type, memory_mb)
    store.update_sandbox_status(sbx_id, "running" if ok else "error")

    return {
        "id": sbx_id,
        "name": record.name,
        "status": "running" if ok else "error",
        "type": record.sbx_type,
        "memory_mb": record.memory_mb,
        "host": record.host,
        "created_at": record.created_at,
    }


@router.delete("/{sandbox_id}/")
async def destroy_sandbox(sandbox_id: str, user: dict = Depends(require_non_viewer)):
    """销毁沙箱实例。"""
    # 先停止常驻实例
    _manager.stop(sandbox_id)
    store = get_task_store()
    deleted = store.delete_sandbox(sandbox_id)
    if deleted:
        return {"id": sandbox_id, "status": "terminated"}
    return {"id": sandbox_id, "status": "not_found"}


# ──────────────── 沙箱执行（真实引擎，不变） ────────────────

@router.post("/{sandbox_id}/execute", response_model=SandboxExecuteResult)
async def execute_in_sandbox(sandbox_id: str, payload: SandboxExecuteRequest):
    """在指定沙箱中执行代码/脚本（真实沙箱隔离执行）。"""
    store = get_task_store()
    sandbox_record = store.get_sandbox(sandbox_id)
    if not sandbox_record:
        raise HTTPException(status_code=404, detail="沙箱不存在")
    if sandbox_record.status == "terminated":
        raise HTTPException(status_code=400, detail="沙箱已销毁，无法执行")

    sandbox_type = sandbox_record.sbx_type
    sandbox_memory = sandbox_record.memory_mb

    if sandbox_type not in ("python", "node"):
        raise HTTPException(status_code=400, detail="当前仅支持 Python 和 Node.js 沙箱执行，Browser 沙箱请使用专用测试工具")

    # ─── 第一步：代码安全检查 ───
    checker = get_safety_checker()
    safety_report = checker.scan(payload.code)

    # 记录安全检查审计
    audit = get_audit_store()
    code_hash = hashlib.sha256(payload.code.encode()).hexdigest()
    audit.write_safety_report(
        task_id=sandbox_id,
        user_id="admin",
        team_id="default",
        code=payload.code,
        report=safety_report,
    )

    # 安全检查未通过 → 直接拒绝，不进入沙箱
    if not safety_report.passed:
        logger.warning(f"[Sandbox] 安全检查拒绝执行 sandbox={sandbox_id} hash={code_hash[:12]}")
        return SandboxExecuteResult(
            ok=False,
            status="safety_rejected",
            error_message=f"代码安全检查未通过: {safety_report.summary()}",
            duration_ms=safety_report.scan_duration_ms,
        )

    # ─── 第二步：Git 仓库克隆（如指定） ───
    clone_dir = None
    read_only_paths = []
    if payload.repo_url:
        try:
            clone_dir = _clone_repo(payload.repo_url, payload.branch or "main")
            read_only_paths = [clone_dir]
        except RuntimeError as e:
            logger.warning(f"[Sandbox] git clone 失败: {e}")
            return SandboxExecuteResult(
                ok=False,
                status="clone_failed",
                error_message=str(e),
                duration_ms=0,
            )

    # ─── 第三步：沙箱隔离执行 ───
    config = SandboxConfig(
        timeout_seconds=max(10, min(payload.timeout or 300, 1800)),
        max_memory_mb=sandbox_memory,
        cleanup_after=True,
        read_only_paths=read_only_paths,
    )
    executor = SandboxExecutor(config)

    try:
        if sandbox_type == "python":
            result = executor.run_script(payload.code, filename="sandbox_script.py")
        else:  # node
            work_dir = executor._jail.setup()
            try:
                script_path = os.path.join(work_dir, "sandbox_script.js")
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(payload.code)
                result = executor.run_command(["node", script_path])
            finally:
                if config.cleanup_after:
                    executor._jail.cleanup()

        # ─── 第四步：记录沙箱执行审计 ───
        audit.write_sandbox_result(
            task_id=sandbox_id,
            user_id="admin",
            team_id="default",
            code_hash=code_hash,
            status=result.status.value,
            duration_ms=result.duration_ms,
            stdout=result.stdout,
            stderr=result.stderr,
            safety_level=safety_report.level.value,
        )

        return SandboxExecuteResult(
            ok=result.ok,
            status=result.status.value,
            stdout=result.stdout,
            stderr=result.stderr,
            error_message=result.error_message or "",
            duration_ms=result.duration_ms,
        )
    except Exception as e:
        logger.exception(f"沙箱 {sandbox_id} 执行失败")
        raise HTTPException(status_code=500, detail=f"沙箱执行失败: {e}")
    finally:
        # 清理 Git 克隆的临时目录（FileJail 会清理自己拷贝的副本）
        if clone_dir and os.path.exists(clone_dir):
            shutil.rmtree(clone_dir, ignore_errors=True)
            logger.debug(f"[Sandbox.Git] 已清理克隆目录: {clone_dir}")


@router.post("/execute-safe", response_model=SafetyCheckedExecuteResponse)
async def execute_with_safety_check(payload: SafetyCheckedExecuteRequest):
    """
    【核心安全链路】AI 工作流调用此端点执行代码。

    完整流程：
    1. 代码安全检查（静态扫描危险模式）
    2. 通过 → 临时沙箱隔离执行
    3. 审计记录持久化
    4. 沙箱自动销毁

    返回：安全检查报告 + 沙箱执行结果 + 审计记录 ID
    """
    # ─── 第一步：代码安全检查 ───
    checker = get_safety_checker()
    safety_report = checker.scan(payload.code)
    code_hash = safety_report.code_hash

    # 记录安全检查审计
    audit = get_audit_store()
    audit_id = audit.write_safety_report(
        task_id=payload.task_id or f"safety-{uuid.uuid4().hex[:8]}",
        user_id=payload.user_id or "system",
        team_id=payload.team_id or "default",
        code=payload.code,
        report=safety_report,
    )

    response = SafetyCheckedExecuteResponse(
        ok=True,
        task_id=payload.task_id,
        safety_checked=True,
        safety_passed=safety_report.passed,
        safety_level=safety_report.level.value,
        safety_summary=safety_report.summary(),
        safety_issues=[
            {
                "line": i.line,
                "pattern": i.pattern,
                "category": i.category,
                "severity": i.severity,
                "explanation": i.explanation,
            }
            for i in safety_report.issues
        ],
        audit_id=audit_id,
    )

    # 安全检查未通过 → 拒绝执行
    if not safety_report.passed:
        response.ok = False
        response.error_message = f"代码安全检查未通过: {safety_report.summary()}"
        logger.warning(f"[SafetyCheck] REJECTED task={payload.task_id} hash={code_hash[:12]} {safety_report.summary()}")
        return response

    logger.info(f"[SafetyCheck] PASSED level={safety_report.level.value} task={payload.task_id} hash={code_hash[:12]}")

    # ─── 第二步：Git 仓库克隆（如指定） ───
    clone_dir = None
    read_only_paths = []
    if payload.repo_url:
        try:
            clone_dir = _clone_repo(payload.repo_url, payload.branch or "main")
            read_only_paths = [clone_dir]
        except RuntimeError as e:
            response.ok = False
            response.error_message = str(e)
            return response

    # ─── 第三步：临时沙箱隔离执行 ───
    config = SandboxConfig(
        timeout_seconds=max(10, min(payload.timeout, 1800)),
        max_memory_mb=512,
        cleanup_after=True,           # ← 执行完自动销毁
        read_only_paths=read_only_paths,
    )
    executor = SandboxExecutor(config)

    try:
        if payload.language == "python":
            result = executor.run_script(payload.code, filename="sandbox_script.py")
        else:  # node
            work_dir = executor._jail.setup()
            try:
                script_path = os.path.join(work_dir, "sandbox_script.js")
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(payload.code)
                result = executor.run_command(["node", script_path])
            finally:
                if config.cleanup_after:
                    executor._jail.cleanup()

        # ─── 第四步：记录沙箱执行审计 ───
        audit.write_sandbox_result(
            task_id=payload.task_id,
            user_id=payload.user_id or "system",
            team_id=payload.team_id or "default",
            code_hash=code_hash,
            status=result.status.value,
            duration_ms=result.duration_ms,
            stdout=result.stdout,
            stderr=result.stderr,
            safety_level=safety_report.level.value,
        )

        response.sandbox_status = result.status.value
        response.sandbox_stdout = result.stdout[:2000]
        response.sandbox_stderr = result.stderr[:500]
        response.sandbox_duration_ms = result.duration_ms
        response.ok = result.ok

        if not result.ok:
            response.error_message = result.error_message or "沙箱执行失败"

        logger.info(
            f"[SandboxExec] task={payload.task_id} status={result.status.value} "
            f"duration={result.duration_ms}ms cleanup=yes"
        )
        return response

    except Exception as e:
        logger.exception(f"[SandboxExec] 异常 task={payload.task_id}")
        # 记录失败审计
        audit.write_sandbox_result(
            task_id=payload.task_id,
            user_id=payload.user_id or "system",
            team_id=payload.team_id or "default",
            code_hash=code_hash,
            status="error",
            duration_ms=0,
            stdout="",
            stderr=str(e),
            safety_level=safety_report.level.value,
        )
        response.ok = False
        response.sandbox_status = "error"
        response.error_message = f"沙箱执行异常: {str(e)}"
        return response
    finally:
        # 清理 Git 克隆的临时目录
        if clone_dir and os.path.exists(clone_dir):
            shutil.rmtree(clone_dir, ignore_errors=True)
