"""
评测中心演示数据灌入脚本（容器内独立运行版）。

不依赖 backend/app 包，直接生成跨多天、多业务模块、含 RAG 检索片段与低分样本的评测记录，
写入 EvalStore 的本地 JSON 文件（默认 /app/data/eval_scores.json）。

容器内用法：
    docker compose exec ai-orchestrator python scripts/seed_eval_demo.py
本地用法（从 agent-harness/backend 目录运行）：
    python scripts/seed_eval_demo.py
"""
import os
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

# 与 EvalStore 默认路径保持一致，方便容器挂载持久化
DEFAULT_DB_PATH = os.path.join(os.getcwd(), "data", "eval_scores.json")
DB_PATH = os.environ.get("EVAL_STORE_PATH", DEFAULT_DB_PATH)

FEATURES = ["knowledge_chat", "chat", "agent_loop", "ai_testcase", "data_factory"]

SAMPLES = {
    "knowledge_chat": [
        {
            "q": "AutoTestHub 的 RAG 流程是怎样的？",
            "a": "AutoTestHub 的 RAG 流程包括：文档切分 chunk、embedding 向量化、按 kb_id 存入向量库、用户提问时检索 top_k 片段拼成 context、再交给 LLM 生成回答。",
            "ref": "RAG 流程：切分 -> embedding -> 向量库 -> 检索 top_k -> 拼 context -> LLM 生成。",
            "docs": [
                {"source": "架构设计.md", "content": "RAG 核心流程：文档切分 chunk -> embedding 向量化 -> 存入向量库（按 kb_id 分集合）-> 检索 top_k -> 拼 context -> LLM 生成回答。", "score": 0.92},
                {"source": "部署手册.md", "content": "向量库支持本地兜底实现，接口对齐 Milvus，embedding 失败时降级返回空列表。", "score": 0.78},
            ],
        },
        {
            "q": "如何配置 Milvus 向量库？",
            "a": "在 .env 中设置 MILVUS_URI 与 MILVUS_TOKEN；若未配置，系统会启用本地内存级向量库兜底。",
            "ref": "环境变量：MILVUS_URI、MILVUS_TOKEN；未配置则本地兜底。",
            "docs": [
                {"source": "部署手册.md", "content": "MILVUS_URI 默认 http://localhost:19530；未设置时启用 LocalVectorStore。", "score": 0.85},
            ],
        },
        {
            "q": "平台支持哪些 LLM 供应商？",
            "a": "当前支持 DeepSeek、通义千问、智谱 GLM，后续可扩展 OpenAI、Claude 等。",
            "ref": "已接入：DeepSeek、DashScope、GLM。",
            "docs": [
                {"source": "模型配置.md", "content": "模型配置表支持 deepseek-chat、qwen-max、glm-4 等模型。", "score": 0.88},
                {"source": "路线图.md", "content": "Phase 2 将接入 OpenAI 与 Claude 系列模型。", "score": 0.55},
            ],
        },
    ],
    "chat": [
        {
            "q": "你好，能帮我写一段 Python 登录接口吗？",
            "a": "当然可以，以下是一个基于 FastAPI 的登录接口示例：...（省略代码）",
            "ref": "通用编程助手回答，无需 RAG。",
            "docs": [],
        },
        {
            "q": "解释一下 JWT 的无状态验证。",
            "a": "JWT 无状态验证指服务端不保存 token 映射表，仅通过签名和过期时间校验请求令牌。",
            "ref": "JWT 本身含 exp，服务端用签名密钥校验即可。",
            "docs": [],
        },
    ],
    "agent_loop": [
        {
            "q": "让 Agent 生成一份 Web 登录测试用例。",
            "a": "已生成 5 条测试用例：正常登录、密码错误、空用户名、SQL 注入、找回密码流程。",
            "ref": "Agent 调用 testcase 工具生成用例。",
            "docs": [
                {"source": "Agent工具说明.md", "content": "testcase 工具支持 Web/API/性能三种用例生成。", "score": 0.91},
            ],
        },
        {
            "q": "执行刚刚生成的用例并给出报告。",
            "a": "执行完成：4 条通过，1 条失败（SQL 注入场景被 WAF 拦截，标记为需要人工复核）。",
            "ref": "Agent 调用 execution 与 report 工具。",
            "docs": [
                {"source": "Agent工具说明.md", "content": "execution 工具支持同步与异步两种执行模式。", "score": 0.82},
            ],
        },
    ],
    "ai_testcase": [
        {
            "q": "生成一个用户注册的 API 测试用例。",
            "a": "已生成：请求 /api/v1/auth/register，校验用户名/密码/邮箱字段，断言 201 状态码。",
            "ref": "AI 用例生成器输出标准 JSON 用例。",
            "docs": [
                {"source": "用例规范.md", "content": "API 用例包含 method、url、headers、payload、assertions。", "score": 0.89},
            ],
        },
        {
            "q": "把这个需求转成 Web 自动化用例：用户在购物车添加商品并结算。",
            "a": "已生成 Web 用例：登录 -> 浏览商品 -> 加入购物车 -> 进入结算页 -> 提交订单 -> 断言订单成功。",
            "ref": "Web 用例使用 Playwright 风格步骤描述。",
            "docs": [
                {"source": "用例规范.md", "content": "Web 用例使用 selector + action + expectation 结构。", "score": 0.86},
            ],
        },
    ],
    "data_factory": [
        {
            "q": "生成 100 条用户脱敏数据。",
            "a": "已生成 100 条用户数据，包含姓名、手机号、邮箱、地址，并已做姓名脱敏与手机号掩码。",
            "ref": "数据工厂支持正则脱敏与 LLM 生成两种模式。",
            "docs": [
                {"source": "数据工厂.md", "content": "数据工厂支持生成结构化数据集并导出 CSV/JSON。", "score": 0.90},
            ],
        },
        {
            "q": "基于订单表生成边界值测试数据。",
            "a": "已生成边界值数据：订单金额 0、负数、超大数、空字符串商品 ID 等共 20 条。",
            "ref": "数据工厂支持规则引擎生成边界值。",
            "docs": [
                {"source": "数据工厂.md", "content": "规则引擎支持 numeric_range、regex、enum 三种字段生成策略。", "score": 0.84},
            ],
        },
    ],
}


def random_score(center: float, spread: float = 12) -> float:
    """生成围绕 center 的随机分数，范围 0-100。"""
    v = random.gauss(center, spread)
    return round(max(0, min(100, v)), 1)


def make_record(base_time: datetime, feature: str, overall_center: float = 78) -> dict:
    sample = random.choice(SAMPLES.get(feature, SAMPLES["chat"]))
    hallucination = random_score(92 if sample["docs"] else 80, 10)
    consistency = random_score(88, 10)
    completeness = random_score(85, 12)
    executability = random_score(82, 14)
    safety = random_score(90, 8)

    overall = round(
        hallucination * 0.3
        + consistency * 0.2
        + completeness * 0.2
        + executability * 0.2
        + safety * 0.1,
        1,
    )

    # 故意制造一些低分样本（用于待优化队列演示）
    if random.random() < 0.15:
        hallucination = random_score(45, 12)
        overall = round(
            hallucination * 0.35
            + consistency * 0.15
            + completeness * 0.15
            + executability * 0.2
            + safety * 0.15,
            1,
        )
        reason = "检索片段与回答关键事实不一致，疑似产生幻觉；建议补充知识库原文并提高检索阈值。"
    else:
        reason = "回答与检索内容一致，覆盖用户问题要点，步骤可执行，未发现明显安全问题。"

    return {
        "id": str(uuid.uuid4()),
        "trace_id": f"trace-{uuid.uuid4().hex[:16]}",
        "feature": feature,
        "input": sample["q"],
        "output": sample["a"],
        "reference": sample["ref"],
        "hallucination": hallucination,
        "consistency": consistency,
        "completeness": completeness,
        "executability": executability,
        "safety": safety,
        "overall": overall,
        "reason": reason,
        "retrieved_docs": sample["docs"][:10],
        "model": random.choice(["deepseek-chat", "qwen-max", "glm-4"]),
        "latency_ms": random.randint(800, 4500),
        "token_usage": {
            "prompt_tokens": random.randint(200, 1200),
            "completion_tokens": random.randint(100, 900),
            "total_tokens": random.randint(350, 2000),
        },
        "created_at": base_time.isoformat(),
    }


def generate_records(count: int = 61, days: int = 7) -> list:
    now = datetime.now(timezone.utc)
    records = []
    for i in range(count):
        offset_hours = random.randint(0, days * 24)
        base_time = now - timedelta(hours=offset_hours)
        feature = random.choice(FEATURES)
        # knowledge_chat 更容易出低分，调低中心值
        center = 72 if feature == "knowledge_chat" else 80
        records.append(make_record(base_time, feature, center))
    # 保证有近 24h 的数据，让默认时间范围不空
    for i in range(8):
        records.append(make_record(now - timedelta(hours=random.randint(0, 23)), random.choice(FEATURES), 78))
    return records


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    records = generate_records()
    data = {"records": records}
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[seed] 已写入 {len(records)} 条评测记录到 {DB_PATH}")


if __name__ == "__main__":
    main()
