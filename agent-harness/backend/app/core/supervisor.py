"""
Supervisor-Worker 多代理编排层 — 解决"单编排撑不住复杂任务 + 多 LLM + 多租户"的问题

设计理念：
- 单编排（workflow.py 的 plan_node→orchestrate_node→verify_node）只能一次性把任务拆成固定步骤，
  遇到"先查、再补生成、再执行评估"这类需要依据中间结果动态决策的需求就乏力了。
- 本层在单编排之上加一个 **Supervisor（编排者 Agent）**：
    1. TaskAnalysis：结合 team_id 用户偏好，把用户请求解析为「意图 + 子目标 + 复杂度」
    2. 动态挑选 / 跳过 / 串行 / 并行 一组 Worker（每个 Worker = 一类专家能力）
    3. 根据 Worker 中间结果决定是否需要追加 Worker（迭代式任务分解）
- 每个 Worker 内部复用 workflow.py 的 _execute_single_step（与单编排共用同一套执行/自愈/审计/沙箱能力），
  因此 Supervisor 不是"另起炉灶"，而是"在已有能力上做动态调度"。

Worker 能力目录（与 workflow.py 的步骤类型一一对应）：
    search        检索团队已有用例 / 知识
    generator     生成新测试用例
    data_factory  生成测试数据
    execution     执行测试（沙箱 / Django）
    evaluator     评估结果质量
"""
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable

from app.core.router import get_llm_router
from app.core.config import get_available_providers
from app.core.metrics import supervisor_decisions_total, supervisor_worker_duration_seconds
from app.core.telemetry import get_tracer
from app.core.eval_event_store import build_event, get_eval_event_store, TraceContext

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class TaskAnalysis:
    """任务解析结果（结合 team 偏好）"""
    intent: str                       # 用户核心意图（一句话）
    sub_goals: list[str]              # 子目标列表
    complexity: str                   # simple / medium / complex
    required_workers: list[str]       # 预估需要的 worker 类型
    reasoning: str = ""               # 解析依据
    preferred_template_id: Optional[str] = None


@dataclass
class WorkerResult:
    worker: str                       # worker 类型
    description: str                  # 该_worker 这次承接的子任务描述
    status: str                      # pending / running / completed / failed / skipped
    output: dict = field(default_factory=dict)
    error: Optional[str] = None


# Worker 能力目录：类型 -> 默认 human 描述（用于 Supervisor 决策）
WORKER_CATALOG: dict[str, str] = {
    "search": "检索团队已有的测试用例、知识库或历史执行结果",
    "generator": "生成新的测试用例（功能/边界/异常场景）",
    "data_factory": "生成测试数据（参数组合 / 造数 / 脱敏数据）",
    "execution": "执行测试（调用代码执行沙箱或 Django Agent 工具）",
    "evaluator": "评估生成结果或执行结果的质量与覆盖率",
}

VALID_WORKERS = set(WORKER_CATALOG.keys())


# ============================================================
# Supervisor：编排者 Agent
# ============================================================

class Supervisor:
    """
    编排者 Agent：依据用户请求 + team 偏好，动态决定调用哪些 Worker、以何种顺序。

    与单编排的区别：
    - 单编排：template 写死步骤，Plan 一次出结果后顺序执行。
    - Supervisor：LLM 实时解析意图 → 选 Worker → 看中间结果 → 可能追加 Worker（迭代）。
    """

    def __init__(self, team_id: str = "default", user_id: Optional[str] = None,
                 model: Optional[str] = None):
        self.team_id = team_id
        self.user_id = user_id
        self.model = model
        self.router = get_llm_router()

    # ----------------------------------------------------------
    # 1. 任务解析（结合 team 偏好）
    # ----------------------------------------------------------
    def analyze_task(self, user_request: str, template_id: Optional[str] = None) -> TaskAnalysis:
        """
        把用户请求解析为结构化任务分析。
        这里就体现了"用户偏好设置"的必要性：team 默认模板、模型偏好会影响解析结论。
        """
        team_hint = self._team_preference_hint()

        system_prompt = (
            "你是一个测试平台的任务编排分析器。请分析用户的测试需求，"
            "输出 JSON（不要任何额外说明）：\n"
            "{\n"
            '  "intent": "用户核心意图（一句话）",\n'
            '  "sub_goals": ["子目标1", "子目标2"],\n'
            '  "complexity": "simple|medium|complex",\n'
            '  "required_workers": ["search", "generator", "data_factory", "execution", "evaluator", "knowledge"]\n'
            "}\n"
            "required_workers 只能从上述 6 个中选，且只选真正需要的。"
            "注意：当用户请求涉及「知识库/文档/规范/需求/历史经验/已有资料」时，应加入 knowledge。"
        )
        user_prompt = f"用户请求：{user_request}\n\n团队偏好提示：{team_hint}\n\n请输出分析 JSON。"

        try:
            raw = self.router.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                task_type="planning",
                model=self.model,
                team_id=self.team_id,
            )
            parsed = self._extract_json(raw)
            analysis = TaskAnalysis(
                intent=parsed.get("intent", user_request),
                sub_goals=parsed.get("sub_goals", [user_request]),
                complexity=parsed.get("complexity", "medium"),
                required_workers=[w for w in parsed.get("required_workers", []) if w in VALID_WORKERS],
                reasoning=raw,
                preferred_template_id=template_id,
            )
            # 兜底：至少一个 worker
            if not analysis.required_workers:
                analysis.required_workers = ["generator", "evaluator"]
            return analysis
        except Exception as e:
            logger.warning(f"[Supervisor] 任务解析失败，使用规则兜底: {e}")
            return self._fallback_analysis(user_request)

    # ----------------------------------------------------------
    # 2. 调度决策（依据中间结果决定是否追加 worker）
    # ----------------------------------------------------------
    def decide_next(self, user_request: str, analysis: TaskAnalysis,
                    done: list[WorkerResult], pending: list[str]) -> dict:
        """
        Supervisor 的「下一步决策」。
        返回 {"action": "dispatch"|"finish", "worker": str|None, "description": str, "reason": str}

        - dispatch：从 pending 取一个 worker 派发，description 是本次子任务描述
        - finish：所有必要 worker 已完成，收尾
        """
        done_types = {r.worker for r in done if r.status == "completed"}

        # 全部 required 且已派发的都完成 → 收尾
        if not pending and done:
            return {"action": "finish", "worker": None, "description": "", "reason": "所有 worker 已完成"}

        system_prompt = (
            "你是测试任务的编排者(Supervisor)。根据已完成 worker 的结果，"
            "决定下一步派发哪个 worker，或是否结束。输出 JSON：\n"
            "{\n"
            '  "action": "dispatch" 或 "finish",\n'
            '  "worker": "search|generator|data_factory|execution|evaluator|knowledge",\n'
            '  "description": "本次派给该 worker 的具体子任务",\n'
            '  "reason": "决策依据"\n'
            "}\n"
            "如果还需要补充新的 worker（例如执行失败后需要重新生成用例），"
            "可以把 worker 设为尚未完成的类型，并在 description 说明新增意图。"
        )

        context = self._build_worker_context(done)
        user_prompt = (
            f"原始请求：{user_request}\n"
            f"已完成 worker：{sorted(done_types)}\n"
            f"待派发 worker：{pending}\n"
            f"中间结果：\n{context}\n\n"
            f"请决定下一步（若都完成则 finish）。"
        )

        try:
            raw = self.router.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                task_type="planning",
                model=self.model,
                team_id=self.team_id,
            )
            parsed = self._extract_json(raw)
            action = parsed.get("action", "finish")
            worker = parsed.get("worker")
            if action == "dispatch" and worker in VALID_WORKERS:
                return {
                    "action": "dispatch",
                    "worker": worker,
                    "description": parsed.get("description", f"执行 {worker} 子任务"),
                    "reason": parsed.get("reason", ""),
                }
            return {"action": "finish", "worker": None, "description": "", "reason": parsed.get("reason", "编排者判定完成")}
        except Exception as e:
            logger.warning(f"[Supervisor] 决策失败，按剩余 pending 顺序派发: {e}")
            if pending:
                w = pending[0]
                return {"action": "dispatch", "worker": w, "description": f"执行 {w} 子任务", "reason": "规则兜底"}
            return {"action": "finish", "worker": None, "description": "", "reason": "兜底收尾"}

    # ----------------------------------------------------------
    # 3. 把 worker 类型映射为 workflow 步骤并执行
    # ----------------------------------------------------------
    def build_step(self, worker: str, description: str, index: int) -> dict:
        """把 Worker 类型翻译为 workflow.py 认识的步骤定义"""
        agent_map = {
            "search": "search",
            "generator": "generator",
            "data_factory": "data_factory",
            "execution": "execution",
            "evaluator": "evaluator",
            "knowledge": "knowledge",
        }
        return {
            "agent": agent_map[worker],
            "description": description,
            "context": {
                # Supervisor 把"子任务描述"透传给下游 Agent，替代原 workflow 的整段 user_request
                "supervisor_subtask": description,
                "supervisor_worker": worker,
            },
            "_index": index,
        }

    # ----------------------------------------------------------
    # 内部工具
    # ----------------------------------------------------------
    def _team_preference_hint(self) -> str:
        """读取团队偏好，作为解析上下文（体现多租户偏好设置）"""
        try:
            from app.core.task_store import get_task_store
            store = get_task_store()
            prefs = store.get_team_model_prefs(self.team_id)
            if prefs:
                return f"该团队模型偏好：{prefs.to_dict()}"
        except Exception:
            pass
        return "无特殊团队偏好（使用全局默认）"

    def _build_worker_context(self, done: list[WorkerResult]) -> str:
        lines = []
        for r in done:
            summary = (r.output or {}).get("result") or r.error or ""
            if isinstance(summary, (dict, list)):
                summary = json.dumps(summary, ensure_ascii=False)[:500]
            else:
                summary = str(summary)[:500]
            lines.append(f"[{r.worker}] {r.status}: {summary}")
        return "\n".join(lines) if lines else "（尚无中间结果）"

    def _extract_json(self, text: str) -> dict:
        """从 LLM 返回里稳妥地提取 JSON（兼容 ```json 代码块）"""
        if not text:
            return {}
        # 去 ```json ``` 包裹
        cleaned = re.sub(r"```(?:json)?", "", text).strip()
        # 截取第一个 { 到最后一个 }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]
        try:
            return json.loads(cleaned)
        except Exception:
            logger.warning(f"[Supervisor] JSON 解析失败，原始: {text[:200]}")
            return {}

    def _fallback_analysis(self, user_request: str) -> TaskAnalysis:
        """规则兜底：关键词命中 worker，保证离线也能跑"""
        req = user_request.lower()
        workers = []
        if any(k in req for k in ["检索", "查询", "已有", "历史", "search", "查"]):
            workers.append("search")
        if any(k in req for k in ["生成", "造", "用例", "generate", "补"]):
            workers.append("generator")
        if any(k in req for k in ["数据", "data", "参数"]):
            workers.append("data_factory")
        if any(k in req for k in ["执行", "跑", "运行", "execute", "run"]):
            workers.append("execution")
        if any(k in req for k in ["知识库", "文档", "规范", "需求", "历史经验", "资料", "knowledge", "rag"]):
            workers.append("knowledge")
        # 评估几乎总是需要
        workers.append("evaluator")
        # 去重保序
        seen, ordered = set(), []
        for w in workers:
            if w not in seen:
                seen.add(w)
                ordered.append(w)
        return TaskAnalysis(
            intent=user_request,
            sub_goals=[user_request],
            complexity="medium" if len(ordered) > 2 else "simple",
            required_workers=ordered,
            reasoning="规则兜底（LLM 解析不可用）",
        )


# ============================================================
# 编排入口：串行驱动器（可被 workflow 包装为流式）
# ============================================================

def _record_supervisor_event(
    trace_id: str,
    user_request: str,
    analysis,
    done: list,
    failed_workers: dict,
    final_output,
    overall_status: str,
    task_id: str,
    team_id: str,
    user_id,
) -> None:
    """
    把整条 supervisor 编排落地为一条 EvalCenter 追踪事件。
    所有 worker 的执行结果归并到同一个 trace_id，使 EvalCenter 能看到
    "一次用例生成编排"的完整链路，而非零散的事件碎片。
    """
    try:
        steps = []
        feature_workers = []
        for r in done:
            w = r.worker
            feature_workers.append(w)
            step_status = "completed" if r.status == "completed" else "failed"
            out = r.output or {}
            resp = ""
            if isinstance(out, dict):
                resp = out.get("response") or out.get("output") or out.get("final_response") or ""
                if isinstance(resp, dict):
                    resp = resp.get("response", "")
            steps.append({
                "step_id": f"step-{w}-{uuid.uuid4().hex[:6]}",
                "type": "tool" if w != "evaluator" else "judge",
                "title": f"Worker · {w}",
                "status": step_status,
                "detail": (r.error or "")[:300] or f"执行完成（{w}）",
                "input": (out.get("input") if isinstance(out, dict) else None) or None,
                "output": str(resp)[:500] if resp else None,
                "metadata": {
                    "worker": w,
                    "feature": w,
                    "status": step_status,
                    "error": r.error,
                },
            })

        event = build_event(
            event_id=f"evt_supervisor_{uuid.uuid4().hex[:12]}",
            trace_id=trace_id,
            feature="ai_testcase" if "generator" in feature_workers else "ai_workflow",
            task_type="supervisor",
            input_summary=user_request[:500],
            output_summary=str(final_output)[:1000] if final_output else "（无输出）",
            model=model or "auto",
            provider="supervisor",
            status=overall_status,
            trace_steps=steps,
            metrics={
                "workers": feature_workers,
                "failed_workers": sorted(failed_workers.keys()),
                "worker_count": len(done),
                "intent": getattr(analysis, "intent", user_request),
                "complexity": getattr(analysis, "complexity", "unknown"),
            },
            user_id=user_id,
            team_id=team_id,
        )
        get_eval_event_store().add_event(event)
        logger.info(f"[Supervisor] 已落地编排事件 trace={trace_id} workers={feature_workers}")
    except Exception as e:
        logger.warning(f"[Supervisor] 记录编排事件失败（不影响主流程）: {e}")


def run_supervisor(
    user_request: str,
    task_id: str,
    user_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    team_id: str = "default",
    template_id: Optional[str] = None,
    model: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
    max_workers: int = 8,
) -> dict:
    """
    运行 Supervisor-Worker 编排（非流式，内部逐步回调进度）。

    Args:
        progress_callback: 形如 callback(event_type, payload) 的钩子，
                           用于把进度推送给前端（与 run_workflow_stream 共用）。

    Returns:
        {
            "task_id", "status", "analysis", "worker_results", "final_output"
        }
    """
    from app.core.workflow import _execute_single_step, _build_initial_state

    supervisor = Supervisor(team_id=team_id, user_id=user_id, model=model)
    workflow_total_inc("started")

    # 初始 state（复用 workflow.py 的构造，保证下游工具/沙箱/记忆一致）
    state = _build_initial_state(
        user_request=user_request,
        task_id=task_id,
        user_id=user_id,
        auth_token=auth_token,
        progress_callback=progress_callback,
        team_id=team_id,
        template_id=template_id,
    )

    # 整条 supervisor 编排共享同一 trace_id，让 worker 工具事件归属到同一条追踪
    trace_id = f"trace_supervisor_{uuid.uuid4().hex[:12]}"
    state = dict(state)
    state["trace_id"] = trace_id

    def _emit(et, payload):
        if progress_callback:
            progress_callback(et, payload)

    try:
        # ---- 阶段 1：任务解析 ----
        _emit("supervisor_plan_start", {"task_id": task_id})
        analysis = supervisor.analyze_task(user_request, template_id)
        _emit("supervisor_plan_complete", {
            "task_id": task_id,
            "intent": analysis.intent,
            "complexity": analysis.complexity,
            "required_workers": analysis.required_workers,
        })
        logger.info(f"[Supervisor] 解析完成 team={team_id} workers={analysis.required_workers}")

        # pending = 解析出的 worker（按顺序），后续 Supervisor 可追加新类型
        pending = list(analysis.required_workers)
        done: list[WorkerResult] = []
        idx = 0
        dispatched_types = set()

        # ---- 阶段 2：迭代调度 ----
        # 失败自愈：每个 worker 最多重试 MAX_RETRIES 次，超过则标记为失败并停止重排，
        # 避免下游不可用时陷入无限重试（曾出现 search/generator 反复失败直至 max_workers 耗尽）。
        # 关键修复：重试的 worker 进入 retry_queue，下一轮优先派发（不依赖 LLM 重新选中它），
        # 否则 LLM 可能持续选择其他 worker，导致失败 worker 永远得不到重试。
        MAX_RETRIES = 1
        retry_count: dict[str, int] = {}
        failed_workers: dict[str, str] = {}
        retry_queue: list[str] = []

        while len(done) < max_workers:
            # 优先处理重试队列，确保失败 worker 一定被重试
            if retry_queue:
                worker = retry_queue.pop(0)
                description = f"{worker} 重试（上次失败）"
            else:
                decision = supervisor.decide_next(user_request, analysis, done, pending)
                if decision["action"] != "dispatch" or not decision["worker"]:
                    break
                worker = decision["worker"]
                description = decision["description"]
                # 防御：LLM 可能返回已完成/非法的 worker，此时忽略 LLM 决策，
                # 强制推进 pending 中第一个未完成的 worker，避免死循环重复派发。
                if worker not in pending:
                    if pending:
                        worker = pending[0]
                        description = f"{worker}（LLM 决策无效，按依赖顺序推进）"
                    else:
                        break

            # 从 pending 移除（若还在）
            if worker in pending:
                pending.remove(worker)
            dispatched_types.add(worker)

            result = _dispatch_worker(
                supervisor, worker, description, idx, state
            )
            done.append(result)
            idx += 1

            _emit("supervisor_worker_complete", {
                "task_id": task_id,
                "worker": worker,
                "status": result.status,
                "description": description,
            })

            # 失败自愈：worker 失败且未超过重试上限时，进入重试队列（优先重试）
            if result.status == "failed":
                seen = retry_count.get(worker, 0)
                if seen < MAX_RETRIES and worker not in failed_workers:
                    retry_count[worker] = seen + 1
                    logger.warning(
                        f"[Supervisor] worker={worker} 第 {seen + 1} 次失败，进入重试队列"
                    )
                    retry_queue.append(worker)
                else:
                    failed_workers[worker] = result.error or "执行失败"
                    logger.error(f"[Supervisor] worker={worker} 已达重试上限，标记为失败")

        # ---- 阶段 3：汇总 ----
        final_output = _summarize(supervisor, user_request, done)
        # 整体状态：有失败 worker 时如实反映，而非一律 completed
        if failed_workers:
            overall_status = "partial" if len(failed_workers) < len(done) else "failed"
        else:
            overall_status = "completed"
        _emit("supervisor_complete", {
            "task_id": task_id,
            "workers_executed": [r.worker for r in done],
            "status": overall_status,
        })
        workflow_total_inc("completed")

        # === 落地到 EvalCenter：把整条 supervisor 编排记录为一条追踪事件 ===
        _record_supervisor_event(
            trace_id=trace_id,
            user_request=user_request,
            analysis=analysis,
            done=done,
            failed_workers=failed_workers,
            final_output=final_output,
            overall_status=overall_status,
            task_id=task_id,
            team_id=team_id,
            user_id=user_id,
        )

        return {
            "task_id": task_id,
            "status": overall_status,
            "failed_workers": sorted(failed_workers.keys()),
            "analysis": {
                "intent": analysis.intent,
                "complexity": analysis.complexity,
                "sub_goals": analysis.sub_goals,
                "required_workers": analysis.required_workers,
            },
            "worker_results": [
                {"worker": r.worker, "status": r.status, "output": r.output, "error": r.error}
                for r in done
            ],
            "final_output": final_output,
        }

    except Exception as e:
        logger.exception(f"[Supervisor] 编排失败 task={task_id}: {e}")
        workflow_total_inc("failed")
        _emit("supervisor_error", {"task_id": task_id, "error": str(e)})
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "worker_results": [],
            "final_output": None,
        }


def _dispatch_worker(supervisor: Supervisor, worker: str, description: str,
                     idx: int, state: dict) -> WorkerResult:
    """派发单个 worker：翻译为 workflow 步骤并复用 _execute_single_step"""
    from app.core.workflow import _execute_single_step
    step = supervisor.build_step(worker, description, idx)
    # 把 supervisor 的子任务描述注入 state.context，让下游 Agent 看到"它该做什么"
    state = dict(state)
    state.setdefault("context", {})
    state["context"]["supervisor_subtask"] = description
    state["context"]["supervisor_worker"] = worker

    with tracer.start_as_current_span(f"supervisor.worker.{worker}") as span:
        span.set_attribute("worker", worker)
        span.set_attribute("team_id", supervisor.team_id)
        with supervisor_worker_duration_seconds.labels(worker=worker).time():
            try:
                # knowledge worker：不经过 workflow 的通用步骤执行，直接走 RAG 检索问答
                if worker == "knowledge":
                    res = _dispatch_knowledge_worker(description, state)
                    status = res.get("status", "completed")
                    supervisor_decisions_total.labels(worker=worker, status=status).inc()
                    return WorkerResult(
                        worker=worker, description=description, status=status, output=res
                    )
                res = _execute_single_step(step, state)
                status = res.get("status", "completed")
                supervisor_decisions_total.labels(worker=worker, status=status).inc()
                return WorkerResult(
                    worker=worker,
                    description=description,
                    status=status,
                    output=res,
                )
            except Exception as e:
                logger.exception(f"[Supervisor] worker={worker} 执行异常: {e}")
                supervisor_decisions_total.labels(worker=worker, status="failed").inc()
                return WorkerResult(
                    worker=worker, description=description, status="failed", error=str(e)
                )


def _dispatch_knowledge_worker(description: str, state: dict) -> dict:
    """knowledge worker：检索团队知识库并回答。

    优先使用用户请求中显式指定的 kb_id（state.context.kb_id），
    否则取该团队/全局第一个可用知识库。问题来自 supervisor 派发的子任务描述。
    """
    from app.core import rag
    from app.core.task_store import get_task_store

    ctx = (state or {}).get("context", {}) or {}
    user_request = state.get("user_request", "") if isinstance(state, dict) else ""
    question = description or user_request

    store = get_task_store()
    kb_id = ctx.get("kb_id")
    if not kb_id:
        bases = store.list_knowledge_bases()
        if not bases:
            return {
                "status": "failed",
                "result": "尚未创建任何知识库，无法使用 knowledge worker。请先在「需求评审师」中创建知识库并上传文档。",
            }
        kb_id = bases[0]["kb_id"]

    try:
        answer_result = rag.answer(kb_id, question)
        out = {
            "status": "completed",
            "result": answer_result.get("answer", ""),
            "sources": answer_result.get("sources", []),
            "kb_id": kb_id,
        }
        if answer_result.get("needs_human"):
            out["needs_human"] = True
            out["eval_score"] = answer_result.get("eval_score")
            out["note"] = "RAG 回答经多轮评估仍未达标，已转人工协同复核。"
        return out
    except Exception as e:
        logger.exception(f"[Supervisor] knowledge worker 失败: {e}")
        return {"status": "failed", "result": f"知识库检索失败: {e}"}


def _summarize(supervisor: Supervisor, user_request: str, done: list[WorkerResult]) -> str:
    """用 LLM 把多个 worker 结果汇总成面向用户的结论"""
    parts = []
    for r in done:
        out = (r.output or {}).get("result")
        if isinstance(out, (dict, list)):
            out = json.dumps(out, ensure_ascii=False)
        parts.append(f"【{r.worker} / {r.status}】\n{out or r.error or ''}")
    context = "\n\n".join(parts)

    system_prompt = (
        "你是测试平台的结果汇总器。请将各专家 worker 的执行结果，"
        "整理成一份简洁的结论（结构化，中文），包含：完成内容、关键产出、风险提示。"
        "使用有序列表时，编号必须按 1、2、3… 递增，不要重复用 1.。"
    )
    user_prompt = f"用户原始请求：{user_request}\n\n各 worker 结果：\n{context[:6000]}"
    try:
        return supervisor.router.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            task_type="evaluation",
            model=supervisor.model,
            team_id=supervisor.team_id,
        )
    except Exception as e:
        logger.warning(f"[Supervisor] 汇总失败: {e}")
        return context


# ============================================================
# metrics 兼容小工具（避免循环导入时 REGISTRY 未注册）
# ============================================================

def workflow_total_inc(status: str):
    try:
        from app.core.metrics import workflow_total
        workflow_total.labels(status=status, mode="supervisor").inc()
    except Exception:
        pass
