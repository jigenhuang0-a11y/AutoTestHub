"""
多 Agent 团队编排器

在现有 Supervisor-Worker 基础上，引入显式角色、任务生命周期、
交接协议（handoff）和评审门控（review gate）。

角色：
- orchestrator: 任务路由与策略制定
- planner: 方案拆解
- builder: 生成用例 / 数据 / 代码
- reviewer: 质量评审（不直接执行产出）
- ops: 运行测试 / 部署验证

任务生命周期：
    inbox -> assigned -> in_progress -> review -> done
                                |         |
                                v         v
                              blocked   failed
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.robustness import call_llm_with_fallback
from app.core.router import get_llm_router
from app.core.task_store import TaskStore
from app.core.workflow import _resolve_system_prompt
from app.schemas.team import (
    Artifact,
    HandoffIntent,
    HandoffMessage,
    ReviewRequest,
    ReviewResult,
    ReviewVerdict,
    TeamOrchestrateRequest,
    TeamOrchestrateResponse,
    TeamRole,
    TeamTask,
    TeamTaskCreate,
    TeamTaskStatus,
    TeamTaskUpdate,
)

logger = logging.getLogger(__name__)


# ============================================================
# 工具辅助
# ============================================================

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_uuid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _get_registry():
    from app.tools.registry import get_registry
    return get_registry()


# ============================================================
# 提示词
# ============================================================

ORCHESTRATOR_SYSTEM_PROMPT = """你是 AutoTestHub 的 Agent 团队编排专家（Orchestrator）。
你的职责：
1. 理解用户任务目标
2. 判断应该由哪个角色执行下一步（planner / builder / reviewer / ops）
3. 输出简洁的 JSON：{"next_role": "builder", "reason": "...", "context": "..."}

可选角色说明：
- planner: 需要先做方案拆解
- builder: 直接生成测试用例、测试数据或代码
- reviewer: 对 builder 产出做质量评审
- ops: 执行测试套件或运行验证
- knowledge: 基于团队知识库（RAG）检索规范/需求/历史经验并回答

只输出 JSON，不要 Markdown 代码块。"""

PLANNER_SYSTEM_PROMPT = """你是 AutoTestHub 的规划专家（Planner）。
请把任务拆解为可执行的步骤，每个步骤包含 role、goal、acceptance_criteria。
输出 JSON 数组，例如：
[{"role": "builder", "goal": "生成登录功能测试用例", "acceptance_criteria": ["覆盖正常流程", "覆盖异常流程"]}]
可选 role：planner / builder / reviewer / ops / knowledge（knowledge 用于检索团队知识库回答规范/需求/历史经验类问题）。
只输出 JSON 数组，不要 Markdown 代码块。"""

REVIEWER_SYSTEM_PROMPT = """你是 AutoTestHub 的质量评审专家（Reviewer）。
请评审 builder 交付的产物，按以下标准给出结论：
- accept: 质量达标，可直接使用
- request_changes: 有小问题，需要修改
- reject: 严重不合格

输出 JSON：{"verdict": "accept|request_changes|reject", "score": 85, "comments": ["..."], "required_changes": ["..."]}
只输出 JSON，不要 Markdown 代码块。"""


def _extract_json(text: str) -> Any:
    """从可能包含 Markdown 代码块的文本中提取 JSON"""
    text = text.strip()
    if text.startswith("```"):
        # 去掉 ```json 和 ```
        lines = text.splitlines()
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)


# ============================================================
# TeamOrchestrator
# ============================================================

class TeamOrchestrator:
    """多 Agent 团队编排器"""

    def __init__(self, store: Optional[TaskStore] = None):
        self.store = store or TaskStore()
        self._router = get_llm_router()

    # ── 任务 CRUD ──

    def create_task(self, req: TeamTaskCreate) -> TeamTask:
        task_id = _short_uuid("team-")
        now = _now()
        task = TeamTask(
            task_id=task_id,
            title=req.title,
            description=req.description,
            status=TeamTaskStatus.INBOX,
            team_id=req.team_id or "default",
            user_id=req.user_id or "",
            required_roles=req.required_roles or [TeamRole.ORCHESTRATOR, TeamRole.BUILDER],
            tags=req.tags or [],
            priority=req.priority or 3,
            parent_task_id=req.parent_task_id,
            model=req.model,
            context=req.context or {},
            artifacts=[],
            handoffs=[],
            reviews=[],
            created_at=now,
            updated_at=now,
        )
        self.store.create_team_task(task)
        return task

    def get_task(self, task_id: str) -> Optional[TeamTask]:
        return self.store.get_team_task(task_id)

    def list_tasks(
        self,
        status: Optional[TeamTaskStatus] = None,
        team_id: Optional[str] = None,
        page_size: int = 50,
        offset: int = 0,
    ) -> tuple[list[TeamTask], int]:
        return self.store.list_team_tasks(
            status=status.value if status else None,
            team_id=team_id,
            page_size=page_size,
            offset=offset,
        )

    def update_task(self, task_id: str, req: TeamTaskUpdate) -> Optional[TeamTask]:
        updates = req.model_dump(exclude_unset=True, exclude_none=True)
        if "status" in updates and isinstance(updates["status"], TeamTaskStatus):
            updates["status"] = updates["status"].value
        if "assigned_to" in updates and isinstance(updates["assigned_to"], TeamRole):
            updates["assigned_to"] = updates["assigned_to"].value
        if not updates:
            return self.get_task(task_id)
        self.store.update_team_task(task_id, **updates)
        return self.get_task(task_id)

    # ── 编排推进 ──

    def orchestrate(self, req: TeamOrchestrateRequest) -> TeamOrchestrateResponse:
        task = self.get_task(req.task_id)
        if task is None:
            return TeamOrchestrateResponse(
                task_id=req.task_id,
                status=TeamTaskStatus.FAILED,
                message="任务不存在",
            )

        action = req.action
        message = ""
        handoff: Optional[HandoffMessage] = None
        review: Optional[ReviewResult] = None

        if action == "next_step":
            task, handoff, message = self._auto_next_step(task)
        elif action == "assign":
            task, handoff = self._assign(
                task,
                role=req.target_role or TeamRole.BUILDER,
                agent=req.target_agent or "",
                message=req.input_message or "",
            )
            message = f"任务已分配给 {task.assigned_to}"
        elif action == "execute":
            task, message = self._execute(task)
        elif action == "submit_review":
            task, handoff = self._submit_for_review(task, req.artifacts)
            message = "已提交评审"
        elif action == "review":
            review = self._review_task(task, verdict=req.context_override.get("verdict", "accept"))
            task = self.get_task(req.task_id)
            message = f"评审结果: {review.verdict}"
        elif action == "unblock":
            task, message = self._unblock(task)
        else:
            message = f"未知 action: {action}"

        return TeamOrchestrateResponse(
            task_id=task.task_id,
            status=task.status,
            assigned_to=task.assigned_to,
            assigned_agent=task.assigned_agent,
            handoff=handoff,
            review=review,
            artifacts=task.artifacts,
            message=message,
        )

    # ── 内部步骤 ──

    def _auto_next_step(self, task: TeamTask) -> tuple[TeamTask, Optional[HandoffMessage], str]:
        """根据当前状态自动推进到下一步"""
        if task.status == TeamTaskStatus.INBOX:
            # 默认先分配给 orchestrator 做路由
            task, handoff = self._assign(task, TeamRole.ORCHESTRATOR, agent="orchestrator-1")
            return task, handoff, "任务从 inbox 进入 assigned（orchestrator）"

        if task.status == TeamTaskStatus.ASSIGNED:
            # 进入执行
            task, msg = self._execute(task)
            return task, None, msg

        if task.status == TeamTaskStatus.IN_PROGRESS:
            # 执行完成，提交 builder 产物到 review
            task, handoff = self._submit_for_review(task, task.artifacts)
            return task, handoff, "执行完成，进入 review"

        if task.status == TeamTaskStatus.REVIEW:
            # 自动按 accept 评审（实际可由 reviewer 角色单独调用 review action）
            self._review_task(task, verdict="accept")
            task = self.get_task(task.task_id)
            return task, None, "评审通过，任务完成"

        if task.status == TeamTaskStatus.BLOCKED:
            return task, None, "任务处于 blocked，请使用 unblock action"

        if task.status in (TeamTaskStatus.DONE, TeamTaskStatus.FAILED):
            return task, None, f"任务已处于终态 {task.status.value}"

        return task, None, f"未知状态: {task.status.value}"

    def _assign(
        self,
        task: TeamTask,
        role: TeamRole,
        agent: str,
        message: str = "",
    ) -> tuple[TeamTask, HandoffMessage]:
        now = _now()
        handoff = HandoffMessage(
            handoff_id=_short_uuid("h-"),
            task_id=task.task_id,
            from_role=task.assigned_to or TeamRole.ORCHESTRATOR,
            to_role=role,
            from_agent=task.assigned_agent or "",
            to_agent=agent,
            intent=HandoffIntent.DELEGATE,
            context=message or f"将任务从 {task.assigned_to} 交接给 {role}",
            deliverables=task.artifacts.copy(),
            blockers=[],
            notes="",
            created_at=now,
        )
        self.store.add_team_handoff(handoff)
        self.store.update_team_task(
            task.task_id,
            status=TeamTaskStatus.ASSIGNED.value,
            assigned_to=role.value,
            assigned_agent=agent,
            updated_at=now,
        )
        return self.get_task(task.task_id), handoff

    def _execute(self, task: TeamTask) -> tuple[TeamTask, str]:
        """按当前 assigned_to 角色执行具体工作"""
        role = task.assigned_to
        if role == TeamRole.ORCHESTRATOR:
            return self._execute_orchestrator(task)
        if role == TeamRole.PLANNER:
            return self._execute_planner(task)
        if role == TeamRole.BUILDER:
            return self._execute_builder(task)
        if role == TeamRole.OPS:
            return self._execute_ops(task)
        return self._set_blocked(task, f"未定义执行逻辑的角色: {role}")

    def _execute_orchestrator(self, task: TeamTask) -> tuple[TeamTask, str]:
        messages = [
            {"role": "system", "content": _resolve_system_prompt("orchestrator", ORCHESTRATOR_SYSTEM_PROMPT)},
            {"role": "user", "content": f"任务标题: {task.title}\n描述: {task.description}\n上下文: {json.dumps(task.context, ensure_ascii=False)}"},
        ]
        try:
            text = call_llm_with_fallback(
                self._router,
                messages,
                task_type="planning",
                team_id=task.team_id,
            )
            decision = _extract_json(text)
            next_role = TeamRole(decision.get("next_role", "builder"))
            reason = decision.get("reason", "")
            context = decision.get("context", "")
        except Exception as e:
            logger.warning(f"[TeamOrchestrator] orchestrator LLM 失败，回退 builder: {e}")
            next_role = TeamRole.BUILDER
            reason = f"LLM 路由失败，回退到 builder: {e}"
            context = ""

        artifact = Artifact(
            name="orchestrator_plan.json",
            artifact_type="plan",
            content=json.dumps({"next_role": next_role.value, "reason": reason, "context": context}, ensure_ascii=False),
        )
        self._append_artifact(task.task_id, artifact)

        # 交接给下一步角色
        task, _ = self._assign(task, next_role, agent=f"{next_role.value}-1", message=context or reason)
        return task, f"orchestrator 决定下一步: {next_role.value}"

    def _execute_planner(self, task: TeamTask) -> tuple[TeamTask, str]:
        messages = [
            {"role": "system", "content": _resolve_system_prompt("planner", PLANNER_SYSTEM_PROMPT)},
            {"role": "user", "content": f"任务: {task.title}\n{task.description}\n上下文: {json.dumps(task.context, ensure_ascii=False)}"},
        ]
        try:
            text = call_llm_with_fallback(
                self._router,
                messages,
                task_type="planning",
                team_id=task.team_id,
            )
            plan = _extract_json(text)
        except Exception as e:
            logger.warning(f"[TeamOrchestrator] planner LLM 失败: {e}")
            plan = [{"role": "builder", "goal": task.title, "acceptance_criteria": ["完成用户需求"]}]

        artifact = Artifact(
            name="planner_output.json",
            artifact_type="plan",
            content=json.dumps(plan, ensure_ascii=False),
        )
        self._append_artifact(task.task_id, artifact)
        self.store.update_team_task(
            task.task_id,
            status=TeamTaskStatus.IN_PROGRESS.value,
            updated_at=_now(),
        )
        return self.get_task(task.task_id), "planner 已生成执行计划"

    def _execute_builder(self, task: TeamTask) -> tuple[TeamTask, str]:
        """builder 调用本地工具生成产物"""
        registry = _get_registry()

        # 简单意图判断：生成测试用例 / 生成数据
        prompt_lower = (task.title + task.description).lower()
        if any(k in prompt_lower for k in ["数据", "testdata", "测试数据", "生成.*条"]):
            tool_name = "generate_data"
            params = {
                "prompt": task.description or task.title,
                "business_domain": task.context.get("business_domain", "custom"),
                "record_count": task.context.get("record_count", 20),
                "dataset_name": task.context.get("dataset_name", f"AI生成-{task.title[:20]}-数据"),
            }
        else:
            tool_name = "generate_testcases"
            params = {
                "requirement": task.description or task.title,
                "count": task.context.get("count", 10),
                "format": task.context.get("format", "json"),
            }

        try:
            result = registry.call_tool(tool_name, **params)
            content = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
            artifact = Artifact(
                name=f"{tool_name}_output.json",
                artifact_type="test_case" if tool_name == "generate_testcases" else "data",
                content=content,
            )
            self._append_artifact(task.task_id, artifact)
            self.store.update_team_task(
                task.task_id,
                status=TeamTaskStatus.IN_PROGRESS.value,
                updated_at=_now(),
            )
            return self.get_task(task.task_id), f"builder 调用 {tool_name} 完成"
        except Exception as e:
            return self._set_blocked(task, f"builder 调用 {tool_name} 失败: {e}")

    def _execute_ops(self, task: TeamTask) -> tuple[TeamTask, str]:
        """ops 调用执行工具"""
        registry = _get_registry()
        params = {
            "suite_id": task.context.get("suite_id", ""),
            "command": task.context.get("command", "pytest"),
            "target": task.context.get("target", ""),
            "params": task.context.get("exec_params", {}),
        }
        try:
            result = registry.call_tool("execute_tests", **params)
            content = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
            artifact = Artifact(
                name="execute_tests_output.json",
                artifact_type="report",
                content=content,
            )
            self._append_artifact(task.task_id, artifact)
            self.store.update_team_task(
                task.task_id,
                status=TeamTaskStatus.IN_PROGRESS.value,
                updated_at=_now(),
            )
            return self.get_task(task.task_id), "ops 执行测试完成"
        except Exception as e:
            return self._set_blocked(task, f"ops 执行失败: {e}")

    def _submit_for_review(
        self,
        task: TeamTask,
        artifacts: list[Artifact],
    ) -> tuple[TeamTask, HandoffMessage]:
        now = _now()
        handoff = HandoffMessage(
            handoff_id=_short_uuid("h-"),
            task_id=task.task_id,
            from_role=task.assigned_to or TeamRole.BUILDER,
            to_role=TeamRole.REVIEWER,
            from_agent=task.assigned_agent or "",
            to_agent="reviewer-1",
            intent=HandoffIntent.CLOSE,
            context="builder/ops 执行完成，提交评审",
            deliverables=artifacts or task.artifacts,
            blockers=[],
            notes="",
            created_at=now,
        )
        self.store.add_team_handoff(handoff)
        self.store.update_team_task(
            task.task_id,
            status=TeamTaskStatus.REVIEW.value,
            assigned_to=TeamRole.REVIEWER.value,
            assigned_agent="reviewer-1",
            updated_at=now,
        )
        # 创建 review request 记录
        review_req = ReviewRequest(
            review_id=_short_uuid("rv-"),
            task_id=task.task_id,
            reviewer_role=TeamRole.REVIEWER,
            reviewer_agent="reviewer-1",
            builder_agent=task.assigned_agent or "",
            artifacts=artifacts or task.artifacts,
            criteria=["完整性", "正确性", "可执行性"],
            created_at=now,
        )
        self.store.add_team_review_request(review_req)
        return self.get_task(task.task_id), handoff

    def _review_task(self, task: TeamTask, verdict: str) -> ReviewResult:
        """ reviewer 对任务产出做评审 """
        # 自动或手动评审：如果 verdict 为空，调用 LLM 自动评审
        if not verdict or verdict not in {v.value for v in ReviewVerdict}:
            artifacts_text = "\n\n".join(
                f"[{a.name}]\n{a.content[:2000]}" for a in task.artifacts
            )
            messages = [
                {"role": "system", "content": _resolve_system_prompt("reviewer", REVIEWER_SYSTEM_PROMPT)},
                {"role": "user", "content": f"任务: {task.title}\n{task.description}\n产物:\n{artifacts_text}"},
            ]
            try:
                text = call_llm_with_fallback(
                    self._router,
                    messages,
                    task_type="evaluation",
                    team_id=task.team_id,
                )
                decision = _extract_json(text)
                verdict = decision.get("verdict", "accept")
                score = decision.get("score", 80)
                comments = decision.get("comments", [])
                required_changes = decision.get("required_changes", [])
            except Exception as e:
                logger.warning(f"[TeamOrchestrator] reviewer LLM 失败，默认 accept: {e}")
                verdict = "accept"
                score = 75
                comments = ["LLM 评审失败，按兜底通过处理"]
                required_changes = []
        else:
            score = 85
            comments = []
            required_changes = []

        review = ReviewResult(
            review_id=_short_uuid("rv-"),
            task_id=task.task_id,
            verdict=ReviewVerdict(verdict),
            reviewer_agent=task.assigned_agent or "reviewer-1",
            score=score,
            comments=comments,
            required_changes=required_changes,
            created_at=_now(),
        )
        self.store.add_team_review_result(review)

        # 根据评审结论更新任务状态
        if review.verdict == ReviewVerdict.ACCEPT:
            self.store.update_team_task(
                task.task_id,
                status=TeamTaskStatus.DONE.value,
                updated_at=_now(),
            )
        elif review.verdict == ReviewVerdict.REJECT:
            self.store.update_team_task(
                task.task_id,
                status=TeamTaskStatus.FAILED.value,
                updated_at=_now(),
            )
        else:  # request_changes
            self.store.update_team_task(
                task.task_id,
                status=TeamTaskStatus.ASSIGNED.value,
                assigned_to=TeamRole.BUILDER.value,
                assigned_agent="builder-1",
                updated_at=_now(),
            )
        return review

    def _unblock(self, task: TeamTask) -> tuple[TeamTask, str]:
        self.store.update_team_task(
            task.task_id,
            status=TeamTaskStatus.ASSIGNED.value,
            updated_at=_now(),
        )
        return self.get_task(task.task_id), "任务已解除阻塞"

    def _set_blocked(self, task: TeamTask, reason: str) -> tuple[TeamTask, str]:
        now = _now()
        handoff = HandoffMessage(
            handoff_id=_short_uuid("h-"),
            task_id=task.task_id,
            from_role=task.assigned_to or TeamRole.BUILDER,
            to_role=TeamRole.ORCHESTRATOR,
            from_agent=task.assigned_agent or "",
            to_agent="orchestrator-1",
            intent=HandoffIntent.ESCALATE,
            context=reason,
            deliverables=task.artifacts.copy(),
            blockers=[reason],
            notes="",
            created_at=now,
        )
        self.store.add_team_handoff(handoff)
        self.store.update_team_task(
            task.task_id,
            status=TeamTaskStatus.BLOCKED.value,
            updated_at=now,
        )
        return self.get_task(task.task_id), f"任务阻塞: {reason}"

    def _append_artifact(self, task_id: str, artifact: Artifact):
        task = self.get_task(task_id)
        if task is None:
            return
        artifacts = task.artifacts or []
        artifacts.append(artifact)
        self.store.update_team_task(
            task_id,
            artifacts_json=json.dumps([a.model_dump() for a in artifacts], ensure_ascii=False),
            updated_at=_now(),
        )


# 全局单例
_orchestrator_instance: Optional[TeamOrchestrator] = None


def get_team_orchestrator(store: Optional[TaskStore] = None) -> TeamOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = TeamOrchestrator(store=store)
    return _orchestrator_instance
