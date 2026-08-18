"""
接口测试用例 API（Phase 3 迁移）

提供测试用例 CRUD、调试、导入 cURL、AI 解析接口、AI 生成用例等能力。
调试/执行类接口返回模拟结果，不真正发起 HTTP 请求（后续可接入执行引擎）。
"""
import json
import logging
import random
import re
import time as _t
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Optional

from app.api.v1.endpoints.auth import get_current_user as require_auth
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

router = APIRouter(prefix="/testcases", tags=["testcases"])


# ── 请求体模型 ──
class TestCaseCreate(BaseModel):
    project: str = ""
    module: str = ""
    title: str = ""
    description: str = ""
    method: str = "GET"
    api_endpoint: str = ""
    headers: Any = Field(default_factory=dict)
    request_body: str = ""
    expected_response: str = ""
    assertion_rules: Any = Field(default_factory=list)
    extract_rules: Any = Field(default_factory=list)
    global_vars: Any = Field(default_factory=dict)
    context_vars: Any = Field(default_factory=dict)
    priority: str = "P2"
    tags: Any = Field(default_factory=list)
    status: str = "draft"
    creator: str = ""


class TestCaseUpdate(BaseModel):
    project: Optional[str] = None
    module: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    method: Optional[str] = None
    api_endpoint: Optional[str] = None
    headers: Optional[Any] = None
    request_body: Optional[str] = None
    expected_response: Optional[str] = None
    assertion_rules: Optional[Any] = None
    extract_rules: Optional[Any] = None
    global_vars: Optional[Any] = None
    context_vars: Optional[Any] = None
    priority: Optional[str] = None
    tags: Optional[Any] = None
    status: Optional[str] = None
    creator: Optional[str] = None


class DebugPayload(BaseModel):
    method: str = "GET"
    url: str = ""
    headers: Any = Field(default_factory=dict)
    body: str = ""
    timeout: int = 10
    model_id: str = ""


class AIGeneratePayload(BaseModel):
    requirement: str = ""
    project: str = ""
    count: int = 5
    model_id: str = ""


class AIParsePayload(BaseModel):
    text: str = ""
    format: str = "openapi"  # openapi / curl / markdown
    # 前端「AI 一键解析接口」实际提交的字段
    api_url: str = ""
    method: str = ""
    response_json: str = ""
    request_body: str = ""
    model_id: str = ""


class ImportCurlPayload(BaseModel):
    curl: str = ""


# ── 辅助：把任意对象序列化为 TEXT 列 ──
def _dump(v) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


@router.get("/")
async def list_testcases(
    project: str = Query(default=""),
    module: str = Query(default=""),
    status: str = Query(default=""),
    priority: str = Query(default=""),
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows, total = store.list_testcases(
        project=project or None, module=module or None, status=status or None,
        priority=priority or None, keyword=keyword or None, page=page, page_size=page_size,
    )
    return {"items": [r.to_dict() for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.post("/")
async def create_testcase(payload: TestCaseCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    data = payload.model_dump()
    data["headers"] = _dump(data["headers"])
    data["assertion_rules"] = _dump(data["assertion_rules"])
    data["extract_rules"] = _dump(data["extract_rules"])
    data["global_vars"] = _dump(data["global_vars"])
    data["context_vars"] = _dump(data["context_vars"])
    data["tags"] = _dump(data["tags"])
    rec = store.create_testcase(data)
    return rec.to_dict()


@router.get("/{tc_id}/")
async def get_testcase(tc_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    return rec.to_dict()


@router.put("/{tc_id}/")
@router.patch("/{tc_id}/")
async def update_testcase(tc_id: str, payload: TestCaseUpdate, _: None = Depends(require_auth)):
    store = get_task_store()
    if not store.get_testcase(tc_id):
        raise HTTPException(status_code=404, detail="用例不存在")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "headers" in data:
        data["headers"] = _dump(data["headers"])
    if "assertion_rules" in data:
        data["assertion_rules"] = _dump(data["assertion_rules"])
    if "extract_rules" in data:
        data["extract_rules"] = _dump(data["extract_rules"])
    if "global_vars" in data:
        data["global_vars"] = _dump(data["global_vars"])
    if "context_vars" in data:
        data["context_vars"] = _dump(data["context_vars"])
    if "tags" in data:
        data["tags"] = _dump(data["tags"])
    rec = store.update_testcase(tc_id, data)
    return rec.to_dict()


@router.post("/{tc_id}/duplicate/")
async def duplicate_testcase(tc_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    d = rec.to_dict()
    d.pop("tc_id", None)
    d.pop("id", None)
    d["title"] = d.get("title", "") + " (副本)"
    d["status"] = "draft"
    new_rec = store.create_testcase(d)
    return new_rec.to_dict()


@router.delete("/{tc_id}/")
async def delete_testcase(tc_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_testcase(tc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用例不存在")
    return {"ok": True, "deleted": tc_id}


@router.delete("/")
async def batch_delete_testcases(ids: list[str] = [], _: None = Depends(require_auth)):
    store = get_task_store()
    deleted = 0
    for tc_id in ids:
        if store.delete_testcase(tc_id):
            deleted += 1
    return {"ok": True, "deleted": deleted}


@router.post("/{tc_id}/debug/")
async def debug_testcase(tc_id: str, _: None = Depends(require_auth)):
    """调试单个用例（返回模拟执行结果）。"""
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    started = _t.time()
    status_code = random.choice([200, 200, 200, 400, 401, 500])
    ok = 200 <= status_code < 400
    cost = round(random.uniform(20, 120), 1)
    result = {
        "test_case_id": tc_id,
        "status": "pass" if ok else "fail",
        "request_time": round(_t.time() - started, 3),
        "response_time": cost,
        "status_code": status_code,
        "error_message": "" if ok else "模拟响应状态码异常",
        "assertions": [
            {"type": "status_code", "expected": 200, "actual": status_code,
             "passed": 200 <= status_code < 400}
        ],
        "response_body": {"code": 0 if ok else status_code, "message": "mock response"},
        "extracted_vars": {},
    }
    return {"ok": True, "execution_results": [result], "passed_count": 1 if ok else 0,
            "failed_count": 0 if ok else 1}


@router.post("/debug-temp/")
async def debug_temp(payload: DebugPayload, _: None = Depends(require_auth)):
    """直接调试一段请求（不落库）。真实 LLM 不可用时返回规则化 mock 结果。"""
    started = _t.time()
    try:
        from app.core.llm_helper import generate_text
        prompt = f"请用一句话模拟以下 HTTP 请求的响应结果（只返回 JSON）：\n{payload.method} {payload.url}\n{payload.body or ''}"
        note = await generate_text(prompt, model_id=payload.model_id or None, temperature=0.3, task_type="ai_testcase")
    except Exception as e:
        logger.warning(f"[testcases] debug LLM 不可用，mock: {e}")
        note = None
    status_code = 200 if note else random.choice([200, 200, 301, 400, 404, 500])
    cost = round(random.uniform(15, 200), 1)
    body = {"code": 0, "message": (note or "mock response")}
    return {
        "ok": True,
        "status_code": status_code,
        "response_time": cost,
        "request_time": round(_t.time() - started, 3),
        "headers": {"content-type": "application/json"},
        "body": body,
        "response_size": len(json.dumps(body, ensure_ascii=False)),
        "ai_enhanced": bool(note),
    }


@router.post("/ai-generate/")
async def ai_generate(payload: AIGeneratePayload, _: None = Depends(require_auth)):
    """AI 生成接口测试用例（真实 LLM，失败降级 mock 并落库）。"""
    store = get_task_store()
    count = max(1, min(payload.count, 20))
    prompt = f"""你是接口测试专家。请为以下需求生成 {count} 条接口测试用例，以 JSON 数组返回，
每条包含：title(用例标题), method(HTTP方法), api_endpoint(路径), request_body(示例请求体字符串),
expected_response(示例响应字符串), assertion_rules(断言数组，元素为 {{type,expected}}), priority(P0/P1/P2)。
需求：{payload.requirement}
项目：{payload.project or '默认项目'}"""
    try:
        from app.core.llm_helper import generate_text
        raw = await generate_text(prompt, model_id=payload.model_id or None, temperature=0.7, task_type="ai_testcase")
        cases = _parse_llm_testcases(raw, payload, count)
        used_llm = True
    except Exception as e:
        logger.warning(f"[testcases] AI 生成失败，降级 mock: {e}")
        cases = [_mock_testcase(payload, i) for i in range(count)]
        used_llm = False

    created = []
    for s in cases:
        s["headers"] = _dump(s.get("headers", {"Content-Type": "application/json"}))
        s["assertion_rules"] = _dump(s.get("assertion_rules", [{"type": "status_code", "expected": 200}]))
        s["extract_rules"] = _dump(s.get("extract_rules", []))
        s["tags"] = _dump(s.get("tags", ["ai-generated"]))
        s["status"] = "draft"
        s["creator"] = "ai"
        created.append(store.create_testcase(s).to_dict())
    return {"ok": True, "test_cases": created, "total": len(created), "ai_enhanced": used_llm}


# ── 对话式用例生成（人机交互） ──
class AIGenConversationMsg(BaseModel):
    role: str = "user"          # user / assistant
    content: str = ""


class AIGenConversationPayload(BaseModel):
    session_id: str = ""        # 前端维持的会话 id，空则新建
    messages: list = Field(default_factory=list)   # 历史对话（含本轮流式前已发生的）
    requirement: str = ""       # 用户故事 / 需求背景（首轮必填）
    project: str = ""
    current_draft: list = Field(default_factory=list)   # 当前草稿用例数组（JSON）
    instruction: str = ""        # 本轮用户指令（澄清 / 修改 / 增量生成）
    model_id: str = ""
    case_type: str = "api"     # api / web / performance / manual
    field_schema: list = Field(default_factory=list)   # 用户确认的用例字段方案


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/ai-generate-conversation/", summary="对话式用例生成（流式）")
async def ai_generate_conversation(payload: AIGenConversationPayload, _: None = Depends(require_auth)):
    """人机交互式生成：澄清需求 -> 生成初稿 -> 针对某条/增量修改。
    后端只负责产出「下一版草稿」，不落库；落库由前端调用 /testcases/ 完成。
    """
    from app.core.router import LLMRouter

    session_id = payload.session_id or _gen_id("aigen")
    task_type = "data_generation"
    router = LLMRouter()
    model_id = payload.model_id or None

    draft_json = json.dumps(payload.current_draft, ensure_ascii=False)
    requirement = payload.requirement.strip()

    def _build_prompt(case_type: str, field_schema: list) -> str:
        schema_lines = "\n".join(
            f"- {s.get('label')}（{s.get('name')}）类型={s.get('type')} {'必填' if s.get('required') else '可选'} 示例={s.get('example') or '无'}"
            for s in (field_schema or [])
        ) or "（用户未指定字段方案）"
        base = (
            "\n规则：\n"
            "1. 生成流程分两步：①字段确认 → ②用例生成。字段方案由用户在前端确认后下发。\n"
            "2. 首轮或需求信息不足时，phase 必须为 'clarify'，test_cases 必须为空数组 []。\n"
            "   - 对于 api/web/performance 类型：reply 中请按 field_schema 中的字段逐个询问，每次聚焦 1-2 个字段。\n"
            "   - 对于 manual 类型：不要按 field_schema 逐个询问，必须严格按后续【manual 类型专属规则】中的 2 步流程推进。\n"
            "3. 当用户已补充足够信息后，phase 转为 'draft'，返回完整 test_cases。"
            "test_cases 中的字段必须严格来自 field_schema，未启用的字段不要出现。\n"
            "   - 对于 manual 类型：只要用户确认了业务流程和核心目标两个选项，即视为“已补充足够信息”，必须立即转为 'draft' 出用例，禁止再追问任何细节。\n"
            "4. reply 用 Markdown 格式写出澄清问题、建议或修改说明（可含列表、加粗）。\n"
            "5. 用户要求修改/删除/增量生成时，请基于 current_draft 返回修改后的「完整」test_cases 数组。\n"
            "6. 你当前服务的测试类型由 case_type 决定：api(接口)、web(Web自动化)、performance(性能)、manual(手工测试)。\n"
            "   请严格根据 case_type 和 field_schema 提问，不要跳出当前测试类型去问无关内容。\n"
            "7. 当某个澄清问题适合让用户从固定选项中选择时，必须在返回的 JSON 中增加 "
            "\"options\" 字段，且 options 必须是字符串数组。"
            "例如：{\"phase\":\"clarify\",\"reply\":\"请选择测试目标\","
            "\"options\":[\"用户下单流程\",\"订单取消流程\",\"商品搜索\"],\"test_cases\":[]}。"
            "适合给选项的场景包括：选择业务流程、选择用例条数、选择正例/反例比例、选择是否需要边界值/异常场景、选择是/否。"
            "不要为单条用例的优先级提供选项。只有开放性问题（如描述具体步骤）才省略 options 字段。\n"
            f"\n用户确认的字段方案（field_schema）：\n{schema_lines}\n"
        )
        options_example = (
            "澄清阶段示例（面试演示专用，选项严格固定，禁止追问其他信息）：\n"
            "{\"phase\":\"clarify\",\"reply\":\"本次手工测试主要验证哪个业务流程？\","
            "\"options\":[\"用户下单流程\",\"订单取消流程\",\"商品搜索与筛选\"],\"test_cases\":[]}\n"
            "{\"phase\":\"clarify\",\"reply\":\"请确认本次测试的核心目标？\","
            "\"options\":[\"验证主流程功能\",\"验证异常与边界场景\",\"验证完整端到端流程\"],\"test_cases\":[]}\n"
            "{\"phase\":\"draft\",\"reply\":\"已确认核心目标，正为你生成 5 条手工测试用例。\","
            "\"test_cases\":[{\"title\":\"示例\",\"precondition\":\"示例\",\"steps\":\"示例\",\"expected_result\":\"示例\",\"priority\":\"P2\",\"is_positive\":true}]}\n"
        )
        if case_type == "web":
            return (
                "你是资深的 Web/UI 自动化测试专家，正在与测试人员协作生成 Web 测试用例。\n"
                "每轮回复都请返回 JSON，不要多余解释。JSON 结构：\n"
                "{\"phase\": \"clarify\" 或 \"draft\", \"reply\": \"给用户的 Markdown 说明文字\", "
                "\"options\": [\"选项1\",\"选项2\"]（可选）, \"test_cases\": [ ...用例... ]}\n"
                + base + options_example +
                "5. 每条用例必须包含：title、page_url(页面地址)、"
                "steps(数组，元素 {action,selector,target,value,description}，action 如 click/input/verify/navigate)、"
                "assertion_rules(数组，元素 {type,expected}，type 如 text_exists/element_exists/url_equals)、priority(P0-P4)。"
            )
        if case_type == "performance":
            return (
                "你是资深的性能测试专家，正在与测试人员协作生成性能测试方案。\n"
                "每轮回复都请返回 JSON，不要多余解释。JSON 结构：\n"
                "{\"phase\": \"clarify\" 或 \"draft\", \"reply\": \"给用户的 Markdown 说明文字\", "
                "\"options\": [\"选项1\",\"选项2\"]（可选）, \"test_cases\": [ ...方案... ]}\n"
                + base + options_example +
                "5. 每条方案必须包含：name(方案名)、target_url(压测目标)、concurrency(并发数)、"
                "duration(持续秒数)、ramp_up(预热秒数)、scenario(数组，元素 {name,method,path,body})、priority(P0-P4)。"
            )
        if case_type == "manual":
            manual_rules = (
                "【manual 类型专属规则】（优先级高于 base 中的通用规则，base 规则 2 中“按 field_schema 逐个询问”对 manual 类型无效）\n"
                "1. manual 类型采用最简面试演示流程：只问两步，然后直接出用例。\n"
            "   第1步：确认核心业务流程。reply 只问“本次手工测试主要验证哪个业务流程？”。\n"
            "         options 固定且 ONLY 这 3 个：用户下单流程、订单取消流程、商品搜索与筛选。不要出现任何其他流程。\n"
            "   第2步：确认核心测试目标。reply 只问“请确认本次测试的核心目标？”。\n"
            "         options 固定且 ONLY 这 3 个：验证主流程功能、验证异常与边界场景、验证完整端到端流程。不要出现任何其他目标。\n"
            "   用户确认核心目标后，phase 必须立即转为 'draft'，直接批量返回完整 test_cases，绝对禁止再问任何问题。\n"
            "2. 默认生成策略（用户未指定时直接使用，不要询问）：生成 5 条用例，正例:反例=3:1，覆盖边界值与异常场景，priority 统一填 P2。\n"
            "3. 每轮回复严禁一次性问多个问题；严禁重复询问已经确认的问题；严禁追问支付方式、支付渠道、验证环节、筛选条件、组合方式、预期结果、业务模块、操作入口、页面字段、字段值、接口、HTTP 方法、URL、请求体、响应码、性能指标、下单入口、购买路径、操作步骤详情、优先级、测试范围、测试环境、测试数据等额外细节。\n"
            "4. 当用户确认了一个业务流程后，正确的下一句话必须是确认该流程并立即进入第2步（核心目标），绝对禁止再围绕该流程追问细节。\n"
            "5. 批量生成的用例中 priority 字段默认统一填 P2，澄清阶段不要询问单条用例的优先级。\n"
            "6. 你必须严格遵守以上顺序：确认流程 → 确认核心目标 → 直接 draft。不要偏离，不要问开放式问题。\n"
            "7. 如果用户已经回答了第2步问题（核心目标），你本轮必须返回 phase='draft'，并生成用例；绝对禁止用“请补充以下信息”、“请确认以下信息”、“为了设计出贴合实际场景的用例”等话术继续追问。\n"
            "【正例】用户选择“用户下单流程”后，你必须这样回复：\n"
            "{\"phase\":\"clarify\",\"reply\":\"好的，已聚焦用户下单流程。请确认本次测试的核心目标？\","
            "\"options\":[\"验证主流程功能\",\"验证异常与边界场景\",\"验证完整端到端流程\"],\"test_cases\":[]}\n"
            "【正例】用户选择“验证异常与边界场景”后，你必须直接返回 draft：\n"
            "{\"phase\":\"draft\",\"reply\":\"已确认核心目标为验证异常与边界场景，正为你生成 5 条用户下单流程手工测试用例。\",\"test_cases\":[...]}\n"
            "【反例】以下回复绝对禁止出现：\n"
            "- 重复询问已经确认过的核心目标\n"
            "- 用“请补充以下信息”开头继续追问\n"
            "- 追问“本次测试需要覆盖哪些支付方式？”\n"
            "- 追问“筛选条件具体指什么？”\n"
            "- 同时问多个问题，例如列出“1. 支付方式 2. 测试场景”"

                )
            return (
                "你是资深的业务手工测试专家，正在与测试人员协作生成手工测试用例。\n"
                "每轮回复都请返回 JSON，不要多余解释。JSON 结构：\n"
                "{\"phase\": \"clarify\" 或 \"draft\", \"reply\": \"给用户的 Markdown 说明文字\", "
                "\"options\": [\"选项1\",\"选项2\"]（可选）, \"test_cases\": [ ...用例... ]}\n"
                + base + options_example + manual_rules
            )
        # default api
        return (
            "你是资深的接口测试专家，正在与测试人员协作生成接口测试用例。\n"
            "每轮回复都请返回 JSON，不要多余解释。JSON 结构：\n"
            "{\"phase\": \"clarify\" 或 \"draft\", \"reply\": \"给用户的 Markdown 说明文字\", "
            "\"options\": [\"选项1\",\"选项2\"]（可选）, \"test_cases\": [ ...用例... ]}\n"
            + base + options_example +
            "5. 每条用例必须包含：title、method(GET/POST/PUT/DELETE/PATCH)、api_endpoint、"
            "request_body(字符串)、expected_response(字符串)、assertion_rules(数组 {type,expected})、priority(P0-P4)。"
        )

    system_prompt = _build_prompt(payload.case_type, payload.field_schema)
    logger.info(f"[AI Generate] case_type={payload.case_type} prompt_prefix={system_prompt[:40]!r}")

    def _is_ready_for_draft(chat_messages):
        """根据历史对话判断是否已经确认流程+核心目标，应直接进入 draft。
        点两次选项后的历史是：A(问流程)->U(选流程)->A(问目标)->U(选目标)，所以 user/assistant 都至少 2 条。"""
        if not chat_messages:
            return False
        user_contents = [m.get("content", "") for m in chat_messages if isinstance(m, dict) and m.get("role") == "user"]
        assistant_contents = [m.get("content", "") for m in chat_messages if isinstance(m, dict) and m.get("role") == "assistant"]
        if len(user_contents) < 2 or len(assistant_contents) < 2:
            return False
        last_assistant = assistant_contents[-1]
        # 上一条 AI 消息必须是在问核心目标/测试目标
        if not re.search(r"核心目标|核心场景|测试目标|业务目标", last_assistant):
            return False
        last_user = user_contents[-1]
        # 用户选的是固定目标选项，不含兜底话术，则必须立即出稿
        if "以上都不是" in last_user or "请描述" in last_user or "请直接输入" in last_user:
            return False
        return True

    instruction = payload.instruction or '（首轮，请先澄清需求或视情况直接给出初稿）'
    if _is_ready_for_draft(payload.messages):
        instruction += "\n\n【强制要求】用户已经确认了业务流程和核心目标，本轮你必须直接返回 phase='draft' 并批量生成完整 test_cases，绝对禁止再问任何问题。"

    user_content = f"""用户故事 / 需求背景：
{requirement or '（暂无，见对话）'}

当前草稿用例（current_draft）：
{draft_json}

本轮用户指令：
{instruction}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    # 把历史对话也带入，保证上下文连续（仅作参考，不重复 system）
    for m in payload.messages:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})

    def _extract_json(text: str) -> dict:
        try:
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1 and e > s:
                return json.loads(text[s:e + 1])
        except Exception:
            pass
        return {}

    def _normalize_options(reply: str, options):
        """根据 reply 内容校验并修正 options，确保选项与当前澄清问题严格匹配。"""
        if not isinstance(reply, str) or not reply:
            return options
        # 核心目标/测试目标：固定 3 个，与业务场景无关
        if re.search(r"核心目标|核心场景|测试目标|业务目标|验证.*功能|验证.*场景", reply):
            return ["验证主流程功能", "验证异常与边界场景", "验证完整端到端流程"]
        # 业务流程/场景：只保留用户要求的 3 个
        if re.search(r"业务流程|业务场景|支付流程|下单流程|订单.*流程|退款流程|搜索流程|登录流程|注册流程|核心流程", reply):
            return ["用户下单流程", "订单取消流程", "商品搜索与筛选"]
        # 若 AI 违反极简流程追问额外细节，清空选项避免误导用户
        if re.search(
            r"支付方式|支付渠道|验证.*环节|优先.*验证|哪个环节|用例标题|前置条件|"
            r"测试步骤|预期结果|输入数据|操作步骤|执行步骤|筛选条件|组合方式|"
            r"请确认以下信息|请补充以下信息|下单入口|购买路径|操作步骤详情|"
            r"优先级|测试范围|测试环境|测试数据|为了设计出贴合实际场景",
            reply,
        ):
            return []
        return options

    def _hardcoded_manual_cases(flow: str, goal: str) -> list:
        """面试演示用：按固定流程+目标返回 5 条手工测试用例，不依赖 LLM。"""
        if flow == "订单取消流程":
            return [
                {
                    "title": "【正例】用户支付成功后主动取消订单",
                    "precondition": "用户已登录并存在待发货订单",
                    "steps": "1. 进入我的订单 2. 选择待发货订单 3. 点击取消订单 4. 确认取消",
                    "expected_result": "订单状态变为已取消，库存回滚，退款原路返回",
                    "priority": "P2", "is_positive": True,
                },
                {
                    "title": "【正例】商家发货后用户无法直接取消",
                    "precondition": "订单状态为已发货",
                    "steps": "1. 进入我的订单 2. 选择已发货订单 3. 查看取消入口",
                    "expected_result": "取消按钮置灰或提示需申请售后",
                    "priority": "P2", "is_positive": True,
                },
                {
                    "title": "【正例】取消订单后再次购买商品",
                    "precondition": "订单已成功取消",
                    "steps": "1. 找到已取消订单中的商品 2. 重新加入购物车并下单",
                    "expected_result": "新订单正常生成，旧订单状态不变",
                    "priority": "P2", "is_positive": True,
                },
                {
                    "title": "【反例】取消不存在的订单",
                    "precondition": "用户未登录或订单 ID 无效",
                    "steps": "1. 直接输入无效订单 ID 2. 调用取消接口",
                    "expected_result": "系统提示订单不存在或无权操作",
                    "priority": "P2", "is_positive": False,
                },
                {
                    "title": "【反例】取消订单后重复提交取消请求",
                    "precondition": "订单已取消成功",
                    "steps": "1. 在已取消订单上再次点击取消 2. 观察系统响应",
                    "expected_result": "系统提示订单已是取消状态，不产生重复退款",
                    "priority": "P2", "is_positive": False,
                },
            ]
        if flow == "商品搜索与筛选":
            return [
                {
                    "title": "【正例】按关键词搜索商品并返回结果",
                    "precondition": "商品库存在匹配商品",
                    "steps": "1. 进入搜索页 2. 输入关键词 3. 点击搜索",
                    "expected_result": "列表按相关度展示商品，无报错",
                    "priority": "P2", "is_positive": True,
                },
                {
                    "title": "【正例】按价格区间筛选商品",
                    "precondition": "商品覆盖多个价格段",
                    "steps": "1. 进入商品列表 2. 设置最低价 100，最高价 500 3. 点击筛选",
                    "expected_result": "仅展示价格在 100-500 之间的商品",
                    "priority": "P2", "is_positive": True,
                },
                {
                    "title": "【正例】组合筛选条件后清除筛选",
                    "precondition": "用户已设置品牌、价格、分类等筛选条件",
                    "steps": "1. 选择多个筛选条件 2. 点击清除筛选 3. 查看列表",
                    "expected_result": "列表恢复默认全部商品展示，筛选条件清空",
                    "priority": "P2", "is_positive": True,
                },
                {
                    "title": "【反例】搜索无结果关键词",
                    "precondition": "商品库中无匹配商品",
                    "steps": "1. 输入不存在的关键词 2. 点击搜索",
                    "expected_result": "页面提示暂无结果，推荐相似商品或搜索建议",
                    "priority": "P2", "is_positive": False,
                },
                {
                    "title": "【反例】筛选条件边界值异常",
                    "precondition": "用户设置最低价大于最高价",
                    "steps": "1. 最低价输入 1000 2. 最高价输入 100 3. 点击筛选",
                    "expected_result": "系统给出友好提示，要求重新输入价格区间",
                    "priority": "P2", "is_positive": False,
                },
            ]
        # 默认：用户下单流程
        if goal == "验证异常与边界场景":
            return [
                {
                    "title": "【正例】用户下单时商品库存刚好满足",
                    "precondition": "商品库存为 1，用户购买 1 件",
                    "steps": "1. 选择商品 2. 数量填 1 3. 提交订单并支付",
                    "expected_result": "订单生成成功，库存扣减为 0",
                    "priority": "P2", "is_positive": True,
                },
                {
                    "title": "【正例】用户下单地址为空时系统提示",
                    "precondition": "用户未设置默认收货地址",
                    "steps": "1. 加入购物车 2. 提交订单 3. 选择地址步骤留空",
                    "expected_result": "系统提示请选择或填写收货地址，无法提交",
                    "priority": "P2", "is_positive": True,
                },
                {
                    "title": "【正例】用户下单后支付超时取消",
                    "precondition": "订单已提交，设置支付超时 30 分钟",
                    "steps": "1. 提交订单 2. 等待 30 分钟不支付 3. 查看订单状态",
                    "expected_result": "订单自动取消，库存释放",
                    "priority": "P2", "is_positive": True,
                },
                {
                    "title": "【反例】用户下单数量超过库存",
                    "precondition": "商品库存为 10，用户购买 100 件",
                    "steps": "1. 选择商品 2. 数量输入 100 3. 点击提交",
                    "expected_result": "系统提示库存不足，无法提交订单",
                    "priority": "P2", "is_positive": False,
                },
                {
                    "title": "【反例】用户下单使用无效优惠券",
                    "precondition": "用户选择已过期或不满足门槛的优惠券",
                    "steps": "1. 进入下单页 2. 选择无效优惠券 3. 提交订单",
                    "expected_result": "系统提示优惠券不可用，订单按原价计算",
                    "priority": "P2", "is_positive": False,
                },
            ]
        # 默认：用户下单流程 + 主流程 / 端到端
        return [
            {
                "title": "【正例】用户正常下单并支付成功",
                "precondition": "用户已登录，商品库存充足，地址有效",
                "steps": "1. 浏览商品加入购物车 2. 提交订单 3. 选择支付方式完成支付",
                "expected_result": "订单状态变为已支付，库存扣减，生成待发货订单",
                "priority": "P2", "is_positive": True,
            },
            {
                "title": "【正例】用户从商品详情页立即购买下单",
                "precondition": "用户已登录",
                "steps": "1. 进入商品详情页 2. 点击立即购买 3. 选择地址并支付",
                "expected_result": "订单生成成功，金额与商品单价一致",
                "priority": "P2", "is_positive": True,
            },
            {
                "title": "【正例】用户下单后查看订单详情",
                "precondition": "用户已成功下单",
                "steps": "1. 进入我的订单 2. 点击刚下单的订单",
                "expected_result": "订单详情展示商品、价格、地址、状态等信息",
                "priority": "P2", "is_positive": True,
            },
            {
                "title": "【反例】用户未登录直接下单",
                "precondition": "用户未登录",
                "steps": "1. 选择商品 2. 点击立即购买",
                "expected_result": "系统跳转登录页，下单入口不可用",
                "priority": "P2", "is_positive": False,
            },
            {
                "title": "【反例】用户下单时取消支付方式返回",
                "precondition": "用户已提交订单",
                "steps": "1. 提交订单进入支付页 2. 点击取消支付返回",
                "expected_result": "订单状态保持待支付，可进行重新支付",
                "priority": "P2", "is_positive": False,
            },
        ]

    def event_generator():
        yield _sse({"type": "meta", "session_id": session_id})
        full_text = ""
        try:
            # === manual 类型：硬编码面试演示流程，不再依赖 LLM 控制节奏 ===
            if getattr(payload, "case_type", None) == "manual":
                manual_flow_options = ["用户下单流程", "订单取消流程", "商品搜索与筛选"]
                manual_goal_options = ["验证主流程功能", "验证异常与边界场景", "验证完整端到端流程"]
                user_contents = [
                    m.get("content", "").strip()
                    for m in payload.messages
                    if isinstance(m, dict) and m.get("role") == "user" and m.get("content")
                ]
                # 去掉前端可能带上的"我"前缀
                cleaned_user_contents = [re.sub(r"^我\s*", "", c) for c in user_contents]

                # 第1步：用户还没选择流程
                if not cleaned_user_contents:
                    yield _sse({
                        "type": "done",
                        "phase": "clarify",
                        "reply": "好的，我们开始梳理手工测试用例。首先，请告诉我本次手工测试主要验证哪个业务流程？",
                        "options": manual_flow_options,
                        "test_cases": [],
                        "session_id": session_id,
                    })
                    yield _sse("[DONE]")
                    return

                last_user = cleaned_user_contents[-1]

                # 第2步：用户刚选了流程，返回固定目标选项
                if len(cleaned_user_contents) == 1 and last_user in manual_flow_options:
                    flow = last_user
                    yield _sse({
                        "type": "done",
                        "phase": "clarify",
                        "reply": f"好的，我们聚焦{flow}。请确认本次测试的核心目标？",
                        "options": manual_goal_options,
                        "test_cases": [],
                        "session_id": session_id,
                    })
                    yield _sse("[DONE]")
                    return

                # 第3步：用户已选目标，直接出用例（用 LLM 生成内容，失败则兜底）
                flow = cleaned_user_contents[0] if cleaned_user_contents else "用户下单流程"
                goal = last_user if last_user in manual_goal_options else "验证主流程功能"
                gen_prompt = (
                    f"你是手工测试用例专家。已确认业务流程：{flow}，核心目标：{goal}。"
                    f"请直接返回 JSON，phase='draft'，test_cases 包含 5 条手工测试用例。"
                    f"字段：title、precondition、steps、expected_result、priority（默认 P2）、is_positive（正例 true，反例 false）。"
                    f"正例:反例=3:1。不要任何澄清问题。"
                )
                gen_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": gen_prompt},
                ]
                for event in router.chat_stream(messages=gen_messages, task_type=task_type, model=model_id or None):
                    ev_type = event.get("type") if isinstance(event, dict) else None
                    if ev_type == "delta":
                        token = event.get("content", "")
                        if token:
                            full_text += token
                            yield _sse({"type": "token", "content": token})
                    elif ev_type == "done":
                        full_text = event.get("content", full_text)
                    elif ev_type == "error":
                        raise RuntimeError(event.get("message", "LLM 流式调用失败"))

                parsed = _extract_json(full_text)
                cases = parsed.get("test_cases", []) or []
                if not cases:
                    cases = _hardcoded_manual_cases(flow, goal)

                reply = f"已确认核心目标为{goal}，正为你生成 5 条{flow}手工测试用例。"
                yield _sse({
                    "type": "done",
                    "phase": "draft",
                    "reply": reply,
                    "options": [],
                    "test_cases": cases,
                    "session_id": session_id,
                })
                yield _sse("[DONE]")
                return

            # 非 manual 类型保持原有 LLM 流程
            for event in router.chat_stream(
                messages=messages,
                task_type=task_type,
                model=model_id or None,
            ):
                ev_type = event.get("type") if isinstance(event, dict) else None
                if ev_type == "delta":
                    token = event.get("content", "")
                    if token:
                        full_text += token
                        yield _sse({"type": "token", "content": token})
                elif ev_type == "done":
                    # 流结束时的完整内容兜底
                    full_text = event.get("content", full_text)
                elif ev_type == "error":
                    raise RuntimeError(event.get("message", "LLM 流式调用失败"))

            parsed = _extract_json(full_text)
            phase = parsed.get("phase", "draft")
            reply = parsed.get("reply", "") or full_text
            cases = parsed.get("test_cases", []) or []
            options = parsed.get("options")
            # 兜底：根据 reply 关键词自动补充常见选项，不依赖模型是否遵守指令
            if not options and isinstance(reply, str):
                if "测试目标" in reply or "业务目标" in reply or "业务流程" in reply:
                    options = ["用户下单流程", "订单取消流程", "商品搜索与筛选"]
                elif "核心目标" in reply or "核心场景" in reply or "验证" in reply:
                    options = ["验证主流程功能", "验证异常与边界场景", "验证完整端到端流程"]
            # 校验/修正 options，确保与当前 reply 匹配
            options = _normalize_options(reply, options)
            yield _sse({
                "type": "done",
                "phase": phase,
                "reply": reply,
                "options": options,
                "test_cases": cases,
                "session_id": session_id,
            })
        except Exception as e:
            logger.warning(f"[testcases] 对话式生成失败: {e}")
            # 降级：返回一条 mock 草稿，保证前端流程不中断
            yield _sse({
                "type": "done",
                "phase": "draft",
                "reply": "（AI 暂不可用，已生成占位草稿，可手动编辑后保存）",
                "test_cases": [_mock_testcase(payload, 0)],
                "session_id": session_id,
            })
        yield _sse("[DONE]")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/ai-parse-interface/")
async def ai_parse_interface(payload: AIParsePayload, _: None = Depends(require_auth)):
    """AI 解析接口定义（openapi/curl/markdown）为用例草稿。"""
    text = (payload.text or "").strip()
    if not text:
        # 兼容前端「AI 一键解析接口」的字段
        parts = []
        if payload.method:
            parts.append(f"请求方法：{payload.method}")
        if payload.api_url:
            parts.append(f"请求地址：{payload.api_url}")
        if payload.request_body:
            parts.append(f"请求体：\n{payload.request_body}")
        if payload.response_json:
            parts.append(f"响应示例：\n{payload.response_json}")
        text = "\n".join(parts)
    if not text:
        raise HTTPException(status_code=400, detail="解析内容不能为空")
    try:
        from app.core.llm_helper import generate_text
        prompt = f"解析下面的接口定义，提取 method、api_endpoint、请求头、请求体示例，以 JSON 返回：\n{text[:2000]}"
        raw = await generate_text(prompt, model_id=payload.model_id or None, temperature=0.2, task_type="ai_testcase")
        parsed = _parse_interface_raw(raw)
        used_llm = True
    except Exception as e:
        logger.warning(f"[testcases] AI 解析失败，降级规则解析: {e}")
        parsed = _rule_based_parse(text, payload.format)
        used_llm = False
    return {"ok": True, "parsed": parsed, "format": payload.format, "ai_enhanced": used_llm}


def _mock_testcase(payload: AIGenConversationPayload, i: int) -> dict:
    case_type = getattr(payload, "case_type", "api")
    title_prefix = (payload.requirement[:20] or '用例')
    if case_type == "web":
        return {
            "project": payload.project or "AI生成",
            "module": "generated",
            "title": f"{title_prefix} Web用例 #{i+1}",
            "description": payload.requirement,
            "page_url": "https://example.com/login",
            "steps": [
                {"action": "navigate", "target": "https://example.com/login", "value": "", "description": "打开登录页"},
                {"action": "input", "selector": "#username", "target": "", "value": "test_user", "description": "输入用户名"},
                {"action": "click", "selector": "#submit", "target": "", "value": "", "description": "点击登录"},
            ],
            "assertion_rules": [{"type": "text_exists", "expected": "登录成功"}],
            "priority": "P2",
            "tags": ["ai-generated", "web"],
        }
    if case_type == "performance":
        return {
            "name": f"{title_prefix} 压测方案 #{i+1}",
            "description": payload.requirement,
            "target_url": "https://example.com/api/v1/items",
            "concurrency": 10,
            "duration": 60,
            "ramp_up": 10,
            "scenario": [{"name": "查询列表", "method": "GET", "path": "/api/v1/items", "body": ""}],
            "priority": "P2",
            "tags": ["ai-generated", "performance"],
        }
    if case_type == "manual":
        return {
            "project": payload.project or "AI生成",
            "module": "generated",
            "title": f"{title_prefix} 手工用例 #{i+1}",
            "description": payload.requirement,
            "page_url": "",
            "preconditions": "前置条件占位",
            "steps": [
                {"step": "执行步骤 1", "expected": "预期结果 1"},
                {"step": "执行步骤 2", "expected": "预期结果 2"},
            ],
            "assertion_rules": [{"type": "check_result", "expected": "通过"}],
            "priority": "P2",
            "tags": ["ai-generated", "manual"],
        }
    # default api
    ep = f"/api/v1/{payload.project or 'resource'}/{i+1}"
    return {
        "project": payload.project or "AI生成",
        "module": "generated",
        "title": f"{title_prefix} #{i+1}",
        "description": payload.requirement,
        "method": "POST",
        "api_endpoint": ep,
        "request_body": "{}",
        "expected_response": '{"code": 0}',
        "assertion_rules": [{"type": "status_code", "expected": 200}],
        "extract_rules": [],
        "priority": "P2",
        "tags": ["ai-generated"],
    }


def _parse_llm_testcases(raw: str, payload: AIGeneratePayload, count: int) -> list:
    import re
    text = (raw or "").strip()
    try:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            arr = json.loads(text[start:end + 1])
            if isinstance(arr, list) and arr:
                out = []
                for it in arr[:count]:
                    if not isinstance(it, dict):
                        continue
                    out.append({
                        "project": payload.project or "AI生成",
                        "module": "generated",
                        "title": str(it.get("title", "用例")),
                        "description": payload.requirement,
                        "method": str(it.get("method", "POST")).upper(),
                        "api_endpoint": str(it.get("api_endpoint", "")),
                        "request_body": str(it.get("request_body", "{}")),
                        "expected_response": str(it.get("expected_response", '{"code":0}')),
                        "assertion_rules": it.get("assertion_rules", [{"type": "status_code", "expected": 200}]),
                        "extract_rules": [],
                        "priority": it.get("priority", "P2"),
                        "tags": ["ai-generated"],
                    })
                if out:
                    return out
    except Exception as e:
        logger.warning(f"[testcases] 解析 LLM 用例失败: {e}")
    return [_mock_testcase(payload, i) for i in range(count)]


def _rule_based_parse(text: str, fmt: str) -> dict:
    lines = text.splitlines()
    method, url = "GET", ""
    if fmt == "curl" or text.startswith("curl"):
        for tok in text.split():
            if tok.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                method = tok.upper()
            elif tok.startswith("http"):
                url = tok
    elif lines:
        first = lines[0]
        if " " in first:
            method = first.split()[0].upper()
            parts = first.split()
            if len(parts) > 1:
                url = parts[1]
    return {
        "method": method,
        "api_endpoint": url,
        "headers": {"Content-Type": "application/json"},
        "request_body": "",
        "assertion_rules": [{"type": "status_code", "expected": 200}],
    }


def _parse_interface_raw(raw: str) -> dict:
    import re
    text = (raw or "").strip()
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            obj = json.loads(text[start:end + 1])
            obj.setdefault("headers", {"Content-Type": "application/json"})
            obj.setdefault("assertion_rules", [{"type": "status_code", "expected": 200}])
            return obj
    except Exception:
        pass
    return _rule_based_parse(text, "text")


@router.post("/import-curl/")
async def import_curl(payload: ImportCurlPayload, _: None = Depends(require_auth)):
    """从 cURL 导入为用例。"""
    curl = (payload.curl or "").strip()
    if not curl:
        raise HTTPException(status_code=400, detail="cURL 内容不能为空")
    parsed = await ai_parse_interface(AIParsePayload(text=curl, format="curl"), _)
    return {
        "ok": True,
        "test_case": {
            "method": parsed["parsed"]["method"],
            "api_endpoint": parsed["parsed"]["api_endpoint"],
            "headers": parsed["parsed"]["headers"],
            "request_body": "",
            "assertion_rules": parsed["parsed"]["assertion_rules"],
        },
    }


@router.get("/export/curl/")
async def export_curl(tc_id: str = Query(default=""), _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    d = rec.to_dict()
    header_str = " ".join(f"-H '{k}: {v}'" for k, v in (d.get("headers") or {}).items())
    body = d.get("request_body")
    body_str = f"-d '{body}'" if body else ""
    curl = f"curl -X {d['method']} '{d['api_endpoint']}' {header_str} {body_str}".strip()
    return {"ok": True, "curl": curl}


@router.get("/export/interface/")
async def export_interface(tc_id: str = Query(default=""), _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    d = rec.to_dict()
    return {
        "ok": True,
        "interface": {
            "method": d["method"],
            "path": d["api_endpoint"],
            "summary": d["title"],
            "headers": d.get("headers"),
            "request_body": d.get("request_body"),
        },
    }


@router.post("/request-history/")
async def save_request(payload: DebugPayload, user: dict = Depends(require_auth)):
    """保存调试请求到历史。"""
    store = get_task_store()
    rec = store.save_request_history({
        "title": f"{payload.method} {payload.url}",
        "method": payload.method,
        "url": payload.url,
        "headers": _dump(payload.headers),
        "body": payload.body,
    }, user_id=user.get("username", ""))
    return {"ok": True, **rec}


@router.get("/request-history/list/")
async def list_request_history(_: None = Depends(require_auth)):
    store = get_task_store()
    items = store.list_request_history()
    return {"items": items, "total": len(items)}


@router.get("/request-history/{rh_id}/")
async def get_request(rh_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_request_history(rh_id)
    if not rec:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    return rec
