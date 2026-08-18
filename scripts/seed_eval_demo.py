"""
评测中心演示数据灌入脚本。

直接写入 EvalStore 的本地 JSON 文件（data/eval_scores.json），
生成跨多天、多业务模块、含 RAG 检索片段与低分样本的评测记录，
用于评测中心 UI 演示（趋势图、明细抽屉、待优化队列）。

用法（从 agent-harness/backend 目录运行）：
    python ../../scripts/seed_eval_demo.py
或：
    python scripts/seed_eval_demo.py
"""
import os
import sys
import json
import random
from datetime import datetime, timedelta, timezone

# 让脚本能 import 到 app 包（scripts/ -> agent-harness -> agent-harness/backend）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "agent-harness", "backend"))
sys.path.insert(0, BACKEND_ROOT)

from app.core.eval_store import EvalStore, DEFAULT_DB_PATH  # noqa: E402


FEATURES = ["knowledge_chat", "chat", "agent_loop", "ai_testcase", "data_factory"]

# 每个模块的演示问题 / 回答 / 检索片段模板
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
            "q": "如何配置评测中心的多维度评分？",
            "a": "评测中心默认对每次 LLM 调用执行五维 Judge：幻觉率、一致性、完整性、可执行性、安全性，分数保存在本地 EvalStore 并回传 Langfuse Score。",
            "ref": "五维 Judge：幻觉率/一致性/完整性/可执行性/安全性。",
            "docs": [
                {"source": "评测中心.md", "content": "五维 Judge 评分维度：hallucination、consistency、completeness、executability、safety。", "score": 0.88},
            ],
        },
        {
            "q": "Langfuse 接入需要哪些环境变量？",
            "a": "需要 LANGFUSE_PUBLIC_KEY、LANGFUSE_SECRET_KEY、LANGFUSE_HOST 三个变量，未配置时自动降级为 NoOp 不影响主业务。",
            "ref": "Langfuse 需要 public/secret key 与 host 三个变量。",
            "docs": [
                {"source": "可观测性.md", "content": "Langfuse 客户端读取 LANGFUSE_PUBLIC_KEY、LANGFUSE_SECRET_KEY、LANGFUSE_HOST，缺失时走 NoOpLangfuse。", "score": 0.85},
            ],
        },
        # 低分样本：回答与知识库不符（虚构 API）
        {
            "q": "评测中心支持接入 Pinecone 吗？",
            "a": "是的，评测中心原生支持 Pinecone 向量库，只需在配置里填写 PINECONE_KEY 即可自动切换。",
            "ref": "当前向量库为本地兜底实现，接口对齐 Milvus，未提及 Pinecone 支持。",
            "docs": [
                {"source": "向量库.md", "content": "向量存储采用本地兜底实现，接口对齐 Milvus；embedding 失败降级。", "score": 0.55},
            ],
        },
    ],
    "chat": [
        {
            "q": "帮我写一段 Python 断言测试登录接口。",
            "a": "可以使用 requests + pytest：发送 POST /login，断言状态码 200 且返回 token 非空。\n```python\nimport requests\ndef test_login():\n    r = requests.post('/login', json={'u':'a','p':'b'})\n    assert r.status_code == 200\n    assert r.json()['token']\n```",
            "ref": "",
            "docs": [],
        },
        {
            "q": "什么是幂等性？",
            "a": "幂等性指同一操作执行一次与执行多次结果一致，例如 PUT 更新资源、DELETE 删除资源都属于幂等操作。",
            "ref": "幂等：多次执行结果一致。",
            "docs": [],
        },
        # 低分样本：回答不安全（建议明文存密码）
        {
            "q": "用户密码怎么存数据库比较好？",
            "a": "可以直接用 MD5 加密后存入数据库，这样查询也方便。",
            "ref": "密码应使用 bcrypt/scrypt 等加盐哈希，禁止明文或单纯 MD5。",
            "docs": [],
        },
    ],
    "agent_loop": [
        {
            "q": "自动生成登录模块的接口测试用例。",
            "a": "Agent 循环已生成 12 条用例，覆盖正常登录、密码错误、空参数、SQL 注入、并发登录等场景，综合评分通过。",
            "ref": "应覆盖正向、异常、安全、边界。",
            "docs": [],
        },
        {
            "q": "对购物车结算流程做端到端测试。",
            "a": "Agent 循环规划了 3 步：添加商品 -> 优惠券计算 -> 提交订单，已生成对应自动化脚本骨架。",
            "ref": "覆盖核心路径与异常路径。",
            "docs": [],
        },
        # 低分样本：循环未达标转人工
        {
            "q": "生成支付对账的自动化用例。",
            "a": "经过 3 轮自评估仍未达到阈值，已转人工协同复核。",
            "ref": "需覆盖对账差异、超时、重试。",
            "docs": [],
        },
    ],
    "ai_testcase": [
        {
            "q": "为搜索接口生成测试用例。",
            "a": "已生成 20 条用例，包含分页、排序、空关键词、特殊字符、超长输入等。",
            "ref": "覆盖正常/异常/边界。",
            "docs": [],
        },
        {
            "q": "为文件上传生成用例。",
            "a": "已生成 15 条用例，覆盖类型限制、大小限制、并发上传、断点续传。",
            "ref": "覆盖类型/大小/并发。",
            "docs": [],
        },
    ],
    "data_factory": [
        {
            "q": "生成 100 条用户测试数据。",
            "a": "已生成 100 条用户数据，包含姓名、手机号、邮箱，符合格式约束。",
            "ref": "数据需符合格式约束。",
            "docs": [],
        },
        {
            "q": "生成订单测试数据。",
            "a": "已生成 50 条订单数据，金额、状态、时间分布合理。",
            "ref": "数据分布合理。",
            "docs": [],
        },
    ],
}


def build_record(feature, sample, created_dt):
    """构造一条评测记录（模拟 Judge 输出）。"""
    q = sample["q"]
    a = sample["a"]
    ref = sample["ref"]
    docs = sample.get("docs", [])

    # 低分判定：知识不符 / 不安全 / 转人工
    is_low = (
        ("Pinecone" in a and "Pinecone" not in ref)
        or ("MD5" in a)
        or ("人工协同" in a)
    )

    if is_low:
        overall = random.randint(45, 65)
        hallucination = random.randint(40, 58)
        consistency = random.randint(55, 70)
        completeness = random.randint(60, 75)
        executability = random.randint(70, 85)
        safety = random.randint(35, 55)
        reason = "回答与知识库/安全规范存在偏差，已归集至待优化队列。"
    else:
        overall = random.randint(82, 96)
        hallucination = random.randint(88, 98)
        consistency = random.randint(85, 97)
        completeness = random.randint(83, 96)
        executability = random.randint(86, 98)
        safety = random.randint(90, 99)
        reason = "回答准确、与知识库一致、可执行且安全，质量良好。"

    model = random.choice(["deepseek-chat", "qwen-max", "gpt-4o-mini"])
    latency = random.randint(800, 4200)
    tokens = random.randint(320, 1800)

    return {
        "created_at": created_dt.astimezone(timezone.utc).isoformat(),
        "input_text": q,
        "output_text": a,
        "reference": ref,
        "feature": feature,
        "overall": overall,
        "hallucination": hallucination,
        "consistency": consistency,
        "completeness": completeness,
        "executability": executability,
        "safety": safety,
        "reason": reason,
        "trace_id": f"seed-{created_dt.strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}",
        "retrieved_docs": docs,
        "model": model,
        "latency_ms": latency,
        "token_usage": tokens,
    }


def main():
    store = EvalStore()
    # 完全覆盖旧演示数据，保证可重复运行
    if os.path.exists(DEFAULT_DB_PATH):
        os.remove(DEFAULT_DB_PATH)
        store = EvalStore()

    now = datetime.now(timezone.utc)
    total = 0
    # 跨 7 天，每天 6~10 条，覆盖所有模块
    for day_offset in range(7, -1, -1):
        day = now - timedelta(days=day_offset)
        count = random.randint(6, 10)
        for _ in range(count):
            feature = random.choice(FEATURES)
            sample = random.choice(SAMPLES[feature])
            # 当天随机时间
            dt = day.replace(
                hour=random.randint(8, 22),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
                microsecond=0,
            )
            record = build_record(feature, sample, dt)
            store.save(record)
            total += 1

    print(f"[seed] 已灌入 {total} 条评测记录 -> {DEFAULT_DB_PATH}")


if __name__ == "__main__":
    main()
