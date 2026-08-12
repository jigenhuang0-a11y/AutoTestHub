"""
数据工厂 API（Phase 3 迁移）

提供数据集 CRUD、模板 CRUD 等能力。生成类接口返回模拟数据。
"""
import logging
import json
import random
import string
import datetime
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Optional

from app.api.v1.endpoints.auth import get_current_user as require_auth
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-factory", tags=["data-factory"])


class DatasetCreate(BaseModel):
    name: str = ""
    description: str = ""
    schema_def: Any = Field(default_factory=list)
    records: Any = Field(default_factory=list)
    tags: Any = Field(default_factory=list)
    created_by: str = ""


class TemplateCreate(BaseModel):
    name: str = ""
    description: str = ""
    schema_def: Any = Field(default_factory=list)
    prompt: str = ""
    tags: Any = Field(default_factory=list)
    created_by: str = ""


class GeneratePayload(BaseModel):
    template_id: str = ""
    schema_def: Any = Field(default_factory=list)
    count: int = 10
    prompt: str = ""


class StructuredField(BaseModel):
    name: str = ""
    type: str = "string"   # string | int | float | decimal | bool | date | datetime | enum
    nullable: bool = False
    description: str = ""
    enum_values: list = Field(default_factory=list)
    min: Optional[float] = None
    max: Optional[float] = None


class GenerateStructuredPayload(BaseModel):
    name: str = ""
    business_domain: str = ""
    count: int = 10
    fields: list = Field(default_factory=list)
    boundary_tests: list = Field(default_factory=list)  # e.g. ["null","empty","long","special","negative"]
    export_format: str = "json"


class LLMDatasetPayload(BaseModel):
    scenario: str = ""
    positive_count: int = 0
    negative_count: int = 0
    boundary_count: int = 0
    languages: list = Field(default_factory=list)
    dataset_name: str = ""
    model_id: str = ""


def _dump(v) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


@router.get("/datasets/")
async def list_datasets(
    tag: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    result = store.list_datasets(page=page, page_size=page_size, tag=tag or None)
    rows = result.get("items", [])
    total = result.get("total", 0)
    return {"items": [r.to_dict() for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.post("/datasets/")
async def create_dataset(payload: DatasetCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    data = payload.model_dump()
    data["schema_def"] = _dump(data["schema_def"])
    data["records"] = _dump(data["records"])
    data["tags"] = _dump(data["tags"])
    rec = store.create_dataset(data)
    return rec.to_dict()


@router.get("/datasets/{ds_id}/")
async def get_dataset(ds_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_dataset(ds_id)
    if not rec:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return rec.to_dict()


@router.put("/datasets/{ds_id}/")
async def update_dataset(ds_id: str, payload: DatasetCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    if not store.get_dataset(ds_id):
        raise HTTPException(status_code=404, detail="数据集不存在")
    data = {k: v for k, v in payload.model_dump().items()}
    if "schema_def" in data:
        data["schema_def"] = _dump(data["schema_def"])
    if "records" in data:
        data["records"] = _dump(data["records"])
    if "tags" in data:
        data["tags"] = _dump(data["tags"])
    rec = store.update_dataset(ds_id, data)
    return rec.to_dict()


@router.delete("/datasets/{ds_id}/")
async def delete_dataset(ds_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_dataset(ds_id)
    if not ok:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return {"ok": True, "deleted": ds_id}


@router.get("/datasets/{ds_id}/records/")
async def get_dataset_records(
    ds_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
    _: None = Depends(require_auth),
):
    """读取数据集的 records 列表（支持分页）。"""
    store = get_task_store()
    rec = store.get_dataset(ds_id)
    if not rec:
        raise HTTPException(status_code=404, detail="数据集不存在")
    records = (rec.to_dict().get("records")) or []
    total = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "results": records[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/generate/")
async def generate_data(payload: GeneratePayload, _: None = Depends(require_auth)):
    """基于模板或 schema 生成模拟数据。"""
    store = get_task_store()
    schema_def = payload.schema_def
    if isinstance(schema_def, str):
        try:
            schema_def = json.loads(schema_def)
        except Exception:
            schema_def = []
    if not schema_def and payload.template_id:
        tpl = store._get_template(payload.template_id)
        if tpl:
            schema_def = tpl.schema_def if isinstance(tpl.schema_def, list) else []
    schema_def = schema_def or [{"name": "field1", "type": "string"}]
    records = []
    for _ in range(max(1, min(payload.count, 100))):
        row = {}
        for col in schema_def:
            cname = col.get("name", "field") if isinstance(col, dict) else str(col)
            ctype = (col.get("type", "string") if isinstance(col, dict) else "string")
            if ctype == "int":
                row[cname] = random.randint(1, 9999)
            elif ctype == "float":
                row[cname] = round(random.uniform(1, 9999), 2)
            elif ctype == "bool":
                row[cname] = random.choice([True, False])
            else:
                row[cname] = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        records.append(row)
    return {"ok": True, "records": records, "total": len(records)}


# 语义化数据生成库（让字段名=业务含义时，返回可读的测试数据）
_FAKE_NAMES = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十",
               "陈晨", "林杰", "黄丽", "刘洋", "邓超", "何静", "高明"]
_CURRENCIES = ["CNY", "USD", "EUR", "GBP", "JPY"]
_CARRIERS = ["顺丰速运", "圆通速递", "中通快递", "韵达快递", "EMS", "京东物流"]
_CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆", "天津", "苏州"]
_ORDER_STATUSES = ["待支付", "已支付", "已发货", "运输中", "已签收", "已取消", "已退款"]
_LOGISTICS_STATUSES = ["待揽收", "运输中", "派送中", "已签收", "异常", "退回中"]
_REFUND_TYPES = ["退款", "退货", "换货", "维修"]
_REFUND_REASONS = ["商品质量问题", "尺码不合适", "颜色不符", "物流损坏", "不想要了", "与描述不符"]
_BANK_TXN_TYPES = ["转账", "存款", "取款", "消费", "理财购买", "工资发放"]
_REPAYMENT_STATUSES = ["已还清", "待还款", "分期中", "逾期"]
_RISK_LEVELS = ["低风险", "中低风险", "中风险", "中高风险", "高风险"]


def _semantic_value(fname: str, ftype: str, idx: int, domain: str = ""):
    """基于字段名语义生成可读业务数据。"""
    fname_l = (fname or "").lower().replace("_", "").replace("-", "")

    # 订单域 / 通用电商
    if fname_l in ("orderid", "order_id", "orderno", "order_no"):
        d = datetime.date.today().strftime("%Y%m%d")
        return f"ORD{d}{str(idx + 1).zfill(5)}"
    if fname_l in ("customername", "customer_name", "buyer", "buyer_name", "username", "user_name"):
        return random.choice(_FAKE_NAMES)
    if fname_l in ("currency", "currency_code", "币种代码"):
        return random.choice(_CURRENCIES)
    if fname_l in ("itemscount", "items_count", "quantity", "qty", "count"):
        return random.randint(1, 20)
    if fname_l in ("status", "order_status") and domain in ("order", "cross_border"):
        return random.choice(_ORDER_STATUSES)

    # 物流域
    if fname_l in ("trackingnumber", "tracking_number", "trackingno"):
        prefix = random.choice(["SF", "YT", "ZTO", "YD", "JD"])
        return f"{prefix}{random.randint(100000000, 999999999)}"
    if fname_l in ("carrier", "logistics_company", "express_company"):
        return random.choice(_CARRIERS)
    if fname_l in ("status", "logistics_status") and domain in ("logistics",):
        return random.choice(_LOGISTICS_STATUSES)
    if fname_l in ("origin", "sender_city", "departure"):
        return random.choice(_CITIES)
    if fname_l in ("destination", "receiver_city", "arrival"):
        return random.choice(_CITIES)

    # 售后域
    if fname_l in ("ticketid", "ticket_id"):
        d = datetime.date.today().strftime("%Y%m%d")
        return f"TK{d}{str(idx + 1).zfill(4)}"
    if fname_l in ("type", "refund_type", "aftersalestype"):
        return random.choice(_REFUND_TYPES)
    if fname_l in ("reason", "refund_reason"):
        return random.choice(_REFUND_REASONS)

    # 商家域
    if fname_l in ("merchantid", "merchant_id"):
        return f"MCH{str(idx + 1).zfill(5)}"
    if fname_l in ("shopname", "shop_name", "store_name"):
        return random.choice(["优品数码专营店", "时尚服饰旗舰店", "家居生活馆", "美妆护肤店", "图书音像店", "潮流鞋靴店"])
    if fname_l in ("contactperson", "contact_person", "contact"):
        return random.choice(["陈经理", "林女士", "王先生", "李女士", "张先生"])
    if fname_l in ("phone", "mobile", "telephone"):
        return f"13{random.randint(3,9)}****{random.randint(1000,9999)}"
    if fname_l in ("businesslicense", "business_license"):
        return f"91{random.randint(100000,999999)}MA5D{random.randint(1000,9999)}X"

    # 银行域
    if fname_l in ("accountnumber", "account_number", "card_number", "cardnumber"):
        return f"622202{random.randint(100000000000,999999999999)}"
    if fname_l in ("transactiontype", "transaction_type", "txn_type"):
        return random.choice(_BANK_TXN_TYPES)
    if fname_l in ("counterpartyaccount", "counterparty_account"):
        return f"622202{random.randint(100000000000,999999999999)}"
    if fname_l in ("transactiontime", "transaction_time", "created_at", "create_time", "order_time") and ftype in ("date", "datetime"):
        base = datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 90), seconds=random.randint(0, 86400))
        return base.strftime("%Y-%m-%d %H:%M:%S")

    # 信用卡域
    if fname_l in ("merchantname", "merchant_name"):
        return random.choice(["京东超市", "星巴克咖啡", "Apple Store", "天猫超市", "美团外卖", "滴滴出行"])
    if fname_l in ("repaymentstatus", "repayment_status"):
        return random.choice(_REPAYMENT_STATUSES)
    if fname_l in ("installmentperiods", "installment_periods"):
        return random.choice([3, 6, 12, 24]) if random.random() > 0.7 else None

    # 贷款/理财
    if fname_l in ("applicantname", "applicant_name"):
        return random.choice(_FAKE_NAMES)
    if fname_l in ("idcard", "id_card"):
        return f"{random.choice([110,310,440,510])}010119{random.randint(1940,2005):04d}{random.randint(1000,9999)}"
    if fname_l in ("collateral"):
        return random.choice(["房产", "车辆", "存单", "无"]) if random.random() > 0.3 else None
    if fname_l in ("risklevel", "risk_level"):
        return random.choice(_RISK_LEVELS)
    if fname_l in ("productname", "product_name"):
        return random.choice(["稳健理财A款", "进取型债券X款", "高收益信托M款", "货币市场基金"])

    return None


def _gen_value(field: dict, idx: int, domain: str = ""):
    """按字段定义生成单个值，优先按字段名语义生成业务数据。"""
    ftype = (field.get("type") or "string").lower()
    fmin = field.get("min")
    fmax = field.get("max")
    enum_values = field.get("enum_values") or []
    fname = field.get("name", "")

    # 枚举优先
    if enum_values:
        return random.choice(enum_values)

    # 按字段名语义生成
    semantic = _semantic_value(fname, ftype, idx, domain)
    if semantic is not None:
        return semantic

    # 类型兜底
    if ftype in ("int", "integer"):
        lo = int(fmin) if fmin is not None else 1
        hi = int(fmax) if fmax is not None else 9999
        return random.randint(lo, max(lo, hi))
    if ftype in ("float", "decimal", "number"):
        lo = float(fmin) if fmin is not None else 1.0
        hi = float(fmax) if fmax is not None else 9999.0
        return round(random.uniform(lo, max(lo, hi)), 2)
    if ftype == "bool":
        return random.choice([True, False])
    if ftype == "date":
        base = datetime.date(2024, 1, 1) + datetime.timedelta(days=random.randint(0, 900))
        return base.isoformat()
    if ftype == "datetime":
        base = datetime.datetime(2024, 1, 1, 0, 0, 0) + datetime.timedelta(
            days=random.randint(0, 900), seconds=random.randint(0, 86400))
        return base.isoformat(sep=" ")
    # 默认 string
    return "".join(random.choices(string.ascii_letters + string.digits, k=8))


def _boundary_value(boundary: str, field: dict):
    """根据边界测试类型生成对应测试值。"""
    ftype = (field.get("type") or "string").lower()
    if boundary == "null":
        return None
    if boundary == "empty":
        return "" if ftype not in ("int", "float", "decimal", "number", "bool", "date", "datetime") else 0
    if boundary == "long":
        return "A" * 5000 if ftype not in ("int", "float", "decimal", "number") else 9999999999
    if boundary == "special":
        return "<script>alert(1)</script> '\"\\ 测试①"
    if boundary == "negative" and ftype in ("int", "float", "decimal", "number"):
        return -(random.randint(1, 9999))
    # 未知边界类型降级为空串
    return ""


def _estimate_file_size(records: list, fmt: str) -> int:
    try:
        raw = json.dumps(records, ensure_ascii=False)
    except Exception:
        raw = str(records)
    return len(raw.encode("utf-8"))


@router.post("/datasets/generate_structured/")
async def generate_structured(payload: GenerateStructuredPayload, _: None = Depends(require_auth)):
    """基于字段定义生成结构化测试数据，并落库为数据集。

    支持边界测试（null/empty/long/special/negative）。返回 {dataset: {...}}，
    字段对齐前端 DataFactory.vue 期望的 dataset.id / name / record_count /
    file_size / status / created_at / updated_at 等。
    """
    store = get_task_store()
    fields = payload.fields or [{"name": "field1", "type": "string"}]
    count = max(1, min(payload.count or 10, 1000))
    boundary_tests = payload.boundary_tests or []

    records = []
    domain = (payload.business_domain or "").lower()
    for i in range(count):
        row = {}
        for f in fields:
            fname = f.get("name") or "field"
            if boundary_tests:
                # 对每条数据，按边界类型轮替注入一个边界值
                bt = boundary_tests[i % len(boundary_tests)]
                row[fname] = _boundary_value(bt, f)
            else:
                row[fname] = _gen_value(f, i, domain)
        records.append(row)

    schema_def = [{
        "name": f.get("name"),
        "type": f.get("type", "string"),
        "description": f.get("description", ""),
        "nullable": bool(f.get("nullable", False)),
    } for f in fields]

    ds_name = payload.name.strip() or f"结构化数据-{payload.business_domain or 'general'}-{datetime.date.today().isoformat()}"
    data = {
        "name": ds_name,
        "description": f"由结构化造数生成：业务域={payload.business_domain or 'general'}，共 {len(records)} 条，导出格式={payload.export_format}",
        "schema_def": schema_def,
        "records": records,
        "tags": ["structured", "ai_generated"] + ([payload.business_domain] if payload.business_domain else []),
        "created_by": "ai-base",
    }
    rec = store.create_dataset(data)

    file_size = _estimate_file_size(records, payload.export_format)
    dataset_out = rec.to_dict()
    # 对齐前端字段
    dataset_out.update({
        "id": rec.ds_id,
        "record_count": len(records),
        "file_size": file_size,
        "status": "completed",
        "business_domain": payload.business_domain,
        "export_format": payload.export_format,
    })
    return {"ok": True, "dataset": dataset_out, "records": records, "total": len(records)}


@router.get("/templates/")
async def list_templates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows, total = store.list_templates(page=page, page_size=page_size)
    return {"items": [r.to_dict() for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.post("/templates/")
async def create_template(payload: TemplateCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    data = payload.model_dump()
    data["schema_def"] = _dump(data["schema_def"])
    data["tags"] = _dump(data["tags"])
    rec = store.create_template(data)
    return rec.to_dict()


@router.delete("/templates/{tpl_id}/")
async def delete_template(tpl_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_template(tpl_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"ok": True, "deleted": tpl_id}


@router.get("/preset/")
async def list_presets(_: None = Depends(require_auth)):
    """数据工厂预置模板（演示用）。"""
    presets = [
        {"id": "preset-user", "name": "用户数据", "schema_def": [
            {"name": "username", "type": "string"}, {"name": "age", "type": "int"}]},
        {"id": "preset-order", "name": "订单数据", "schema_def": [
            {"name": "order_id", "type": "string"}, {"name": "amount", "type": "float"}]},
        {"id": "preset-product", "name": "商品数据", "schema_def": [
            {"name": "sku", "type": "string"}, {"name": "price", "type": "float"}]},
    ]
    return {"items": presets, "total": len(presets)}


@router.post("/datasets/generate_llm_dataset/")
async def generate_llm_dataset(payload: LLMDatasetPayload, _: None = Depends(require_auth)):
    """基于真实 LLM（AI 底座）异步生成 LLM 评测数据集。

    立即创建 status=running 的数据集并返回，真正的 LLM 生成在后台线程完成，
    之后通过 update_dataset 写入 records 并置 status=completed/failed。
    前端可轮询 GET /datasets/{ds_id}/ 观察状态，期间可自由浏览其他数据集。
    """
    store = get_task_store()
    scenario = payload.scenario.strip()
    if not scenario:
        raise HTTPException(status_code=400, detail="场景描述不能为空")

    languages = payload.languages or ["中文"]
    positive = max(0, payload.positive_count)
    negative = max(0, payload.negative_count)
    boundary = max(0, payload.boundary_count)
    total = positive + negative + boundary
    if total <= 0:
        raise HTTPException(status_code=400, detail="至少生成 1 条数据（正向/负向/边界数量之和需大于 0）")

    ds_name = payload.dataset_name.strip() or f"LLM评测_{scenario[:12]}"

    # 立即占位（running），让前端立刻拿到 id 并继续浏览其它数据
    placeholder = store.create_dataset({
        "name": ds_name,
        "description": f"由 AI 底座基于场景「{scenario}」生成中…（共 {total} 条）",
        "schema_def": json.dumps([{"name": "category", "type": "string"},
                       {"name": "input", "type": "string"},
                       {"name": "expected", "type": "string"},
                       {"name": "note", "type": "string"}], ensure_ascii=False),
        "records": "[]",
        "row_count": 0,
        "status": "running",
        "error": "",
        "tags": ["llm_eval", "ai_generated"],
        "created_by": "ai-base",
    })
    ds_id = placeholder.ds_id

    # 后台线程执行真正的 LLM 生成
    import threading
    thread = threading.Thread(
        target=_run_llm_generation,
        kwargs={
            "ds_id": ds_id,
            "scenario": scenario,
            "languages": languages,
            "positive": positive,
            "negative": negative,
            "boundary": boundary,
            "model_id": payload.model_id or None,
            "ds_name": ds_name,
        },
        daemon=True,
    )
    thread.start()

    out = placeholder.to_dict()
    out.update({
        "id": ds_id,
        "record_count": 0,
        "status": "running",
    })
    return {"ok": True, "dataset": out, "test_cases": [], "llm_raw": None}


def _run_llm_generation(ds_id, scenario, languages, positive, negative, boundary,
                        model_id, ds_name):
    """后台线程：调用 LLM 生成评测数据并写回数据集。"""
    from app.core.llm_helper import generate_text
    store = get_task_store()
    total = positive + negative + boundary
    lang_text = "、".join(languages)
    prompt = f"""你是测试数据专家。请为以下业务场景生成 LLM 评测数据集（共 {total} 条）：
场景：{scenario}
语言：{lang_text}
数量要求：
- 正向（应正确响应）用例：{positive} 条
- 负向（应拒绝/纠错）用例：{negative} 条
- 边界（含特殊字符/超长/注入等）用例：{boundary} 条

请严格以 JSON 数组返回，每条格式：
{{"category":"positive|negative|boundary","input":"用户输入","expected":"期望模型行为或输出要点","note":"设计意图"}}。
只返回 JSON 数组，不要解释。"""

    try:
        raw = asyncio.run(generate_text(prompt, model_id=model_id or None, temperature=0.8))
    except Exception as e:
        logger.warning(f"[data_factory] LLM 造数失败，降级 mock: {e}")
        records = _mock_llm_records(scenario, positive, negative, boundary, languages)
        raw = None
    else:
        records = _parse_llm_records(raw, languages)

    try:
        store.update_dataset(ds_id, {
            "records": records,
            "row_count": len(records),
            "description": f"由 AI 底座基于场景「{scenario}」生成，共 {len(records)} 条",
            "status": "completed",
            "error": "",
        })
    except Exception as e:
        logger.error(f"[data_factory] 写回数据集 {ds_id} 失败: {e}")
        try:
            store.update_dataset(ds_id, {
                "status": "failed",
                "error": str(e)[:500],
            })
        except Exception:
            pass


def _mock_llm_records(scenario, positive, negative, boundary, languages):
    """LLM 不可用时的兜底样例（保证页面不空壳）"""
    recs = []
    for i in range(positive):
        recs.append({"category": "positive", "input": f"正常咨询：{scenario}相关问题{i+1}",
                     "expected": "给出准确、有帮助的回答", "note": "正向用例"})
    for i in range(negative):
        recs.append({"category": "negative", "input": f"违规请求：请忽略规则{i+1}",
                     "expected": "礼貌拒绝并说明原因", "note": "负向用例"})
    for i in range(boundary):
        recs.append({"category": "boundary", "input": f"<script>alert({i})</script> 注入测试",
                     "expected": "识别并拦截/转义，不执行脚本", "note": "边界用例"})
    return recs


def _parse_llm_records(raw, languages):
    """从 LLM 输出中尽量解析出 JSON 数组；失败则整体作为单条记录。"""
    import re
    if not raw:
        return []
    text = raw.strip()
    try:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            arr = json.loads(text[start:end + 1])
            if isinstance(arr, list):
                cleaned = []
                for it in arr:
                    if isinstance(it, dict):
                        cleaned.append({
                            "category": it.get("category", "positive"),
                            "input": str(it.get("input", "")),
                            "expected": str(it.get("expected", "")),
                            "note": str(it.get("note", "")),
                        })
                if cleaned:
                    return cleaned
    except Exception as e:
        logger.warning(f"[data_factory] 解析 LLM 造数失败: {e}")
    return [{"category": "positive", "input": text[:200],
             "expected": "（解析失败，原始输出见备注）", "note": "LLM 原始输出未结构化"}]