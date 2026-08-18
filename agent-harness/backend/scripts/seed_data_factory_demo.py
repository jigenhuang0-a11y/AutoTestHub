"""
数据工厂演示数据灌入脚本（容器内独立运行版）。

直接向 agent-harness 的 SQLite 数据库（默认 /app/data/harness.db）写入：
- 3 个结构化数据集（跨境电商订单、金融科技交易、用户画像）
- 2 个数据工厂模板

容器内用法：
    docker compose exec ai-orchestrator python scripts/seed_data_factory_demo.py
本地用法（从 agent-harness/backend 目录运行）：
    python scripts/seed_data_factory_demo.py
"""
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

# 定位数据库：容器内默认 /app/data/harness.db，本地则相对于 backend/data
DB_PATH = os.environ.get("TASK_STORE_PATH", os.path.join(os.getcwd(), "data", "harness.db"))

_FAKE_NAMES = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十",
               "陈晨", "林杰", "黄丽", "刘洋", "邓超", "何静", "高明"]
_CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆", "天津", "苏州"]
_CURRENCIES = ["CNY", "USD", "EUR", "GBP", "JPY"]
_ORDER_STATUSES = ["待支付", "已支付", "已发货", "运输中", "已签收", "已取消", "已退款"]
_TXN_TYPES = ["转账", "存款", "取款", "消费", "理财购买", "工资发放"]
_RISK_LEVELS = ["低风险", "中低风险", "中风险", "中高风险", "高风险"]


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def random_past(days: int = 90):
    dt = datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, days), seconds=random.randint(0, 86400)
    )
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def gen_order_records(count: int = 20) -> list:
    records = []
    d = datetime.now(timezone.utc).strftime("%Y%m%d")
    for i in range(count):
        records.append({
            "order_id": f"ORD{d}{str(i + 1).zfill(5)}",
            "customer_name": random.choice(_FAKE_NAMES),
            "amount": round(random.uniform(10, 5000), 2),
            "currency": random.choice(_CURRENCIES),
            "items_count": random.randint(1, 20),
            "status": random.choice(_ORDER_STATUSES),
            "created_at": random_past(30),
            "shipping_city": random.choice(_CITIES),
        })
    return records


def gen_finance_records(count: int = 20) -> list:
    records = []
    for i in range(count):
        records.append({
            "txn_id": f"TXN{datetime.now(timezone.utc).strftime('%Y%m%d')}{str(i + 1).zfill(5)}",
            "account_number": f"622202{random.randint(100000000000, 999999999999)}",
            "txn_type": random.choice(_TXN_TYPES),
            "amount": round(random.uniform(-10000, 10000), 2),
            "counterparty": random.choice(["京东超市", "星巴克咖啡", "Apple Store", "天猫超市", "美团外卖"]),
            "risk_level": random.choice(_RISK_LEVELS),
            "txn_time": random_past(60),
        })
    return records


def gen_user_records(count: int = 20) -> list:
    records = []
    for i in range(count):
        records.append({
            "user_id": f"USR{str(i + 1).zfill(6)}",
            "username": f"user_{random.randint(1000, 9999)}",
            "age": random.randint(18, 65),
            "city": random.choice(_CITIES),
            "register_date": (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
            "is_vip": random.choice([True, False]),
            "credit_score": random.randint(350, 950),
        })
    return records


def seed_datasets():
    import sqlite3

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 确保表存在（与 task_store 建表语句保持一致）
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS datafactory_datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ds_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            schema_def TEXT NOT NULL DEFAULT '[]',
            records TEXT NOT NULL DEFAULT '[]',
            row_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'completed',
            error TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS datafactory_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tpl_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            domain TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            scenario TEXT NOT NULL DEFAULT '',
            config TEXT NOT NULL DEFAULT '{}',
            variables TEXT NOT NULL DEFAULT '[]',
            tags TEXT NOT NULL DEFAULT '[]',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        """
    )

    datasets = [
        {
            "name": "跨境电商订单数据",
            "description": "演示数据集：模拟跨境电商平台的订单记录，含订单号、客户、金额、币种、状态等字段。",
            "business_domain": "cross_border",
            "tags": ["structured", "ai_generated", "cross_border"],
            "schema_def": [
                {"name": "order_id", "type": "string", "description": "订单唯一标识"},
                {"name": "customer_name", "type": "string", "description": "客户姓名"},
                {"name": "amount", "type": "decimal", "description": "订单金额"},
                {"name": "currency", "type": "string", "description": "币种代码"},
                {"name": "items_count", "type": "int", "description": "商品件数"},
                {"name": "status", "type": "string", "description": "订单状态"},
                {"name": "created_at", "type": "datetime", "description": "下单时间"},
                {"name": "shipping_city", "type": "string", "description": "收货城市"},
            ],
            "records": gen_order_records(20),
        },
        {
            "name": "金融科技交易流水",
            "description": "演示数据集：模拟银行/支付系统的交易流水，含交易号、账户、交易类型、金额、风险等级等字段。",
            "business_domain": "fintech",
            "tags": ["structured", "ai_generated", "fintech"],
            "schema_def": [
                {"name": "txn_id", "type": "string", "description": "交易流水号"},
                {"name": "account_number", "type": "string", "description": "银行卡号"},
                {"name": "txn_type", "type": "string", "description": "交易类型"},
                {"name": "amount", "type": "decimal", "description": "交易金额"},
                {"name": "counterparty", "type": "string", "description": "交易对手"},
                {"name": "risk_level", "type": "string", "description": "风险等级"},
                {"name": "txn_time", "type": "datetime", "description": "交易时间"},
            ],
            "records": gen_finance_records(20),
        },
        {
            "name": "用户画像样本",
            "description": "演示数据集：模拟电商平台用户画像，含用户 ID、年龄、城市、注册日期、是否会员、信用分等字段。",
            "business_domain": "user_profile",
            "tags": ["structured", "ai_generated", "user_profile"],
            "schema_def": [
                {"name": "user_id", "type": "string", "description": "用户 ID"},
                {"name": "username", "type": "string", "description": "用户名"},
                {"name": "age", "type": "int", "description": "年龄"},
                {"name": "city", "type": "string", "description": "城市"},
                {"name": "register_date", "type": "date", "description": "注册日期"},
                {"name": "is_vip", "type": "bool", "description": "是否 VIP"},
                {"name": "credit_score", "type": "int", "description": "信用分"},
            ],
            "records": gen_user_records(20),
        },
    ]

    inserted_ds = 0
    now = now_utc()
    for ds in datasets:
        ds_id = "ds-" + str(uuid.uuid4())[:8]
        try:
            conn.execute(
                """
                INSERT INTO datafactory_datasets
                (ds_id, name, description, schema_def, records, row_count, status, error, tags,
                 created_by, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ds_id,
                    ds["name"],
                    ds["description"],
                    json.dumps(ds["schema_def"], ensure_ascii=False),
                    json.dumps(ds["records"], ensure_ascii=False),
                    len(ds["records"]),
                    "completed",
                    "",
                    json.dumps(ds["tags"], ensure_ascii=False),
                    "ai-base",
                    now,
                    now,
                ),
            )
            inserted_ds += 1
        except Exception as e:
            print(f"[seed] 写入数据集失败 {ds['name']}: {e}")

    templates = [
        {
            "name": "电商订单模板",
            "description": "预置模板：快速生成包含订单号、客户、金额、状态等字段的电商订单数据。",
            "domain": "cross_border",
            "category": "结构化数据",
            "scenario": "跨境电商订单造数",
            "config": {
                "fields": [
                    {"name": "order_id", "type": "string", "description": "订单号"},
                    {"name": "customer_name", "type": "string", "description": "客户姓名"},
                    {"name": "amount", "type": "decimal", "description": "订单金额"},
                    {"name": "status", "type": "string", "description": "订单状态"},
                ]
            },
            "variables": [],
            "tags": ["preset", "cross_border"],
        },
        {
            "name": "金融交易模板",
            "description": "预置模板：快速生成包含交易号、账户、交易类型、金额、风险等级等字段的金融交易流水。",
            "domain": "fintech",
            "category": "结构化数据",
            "scenario": "金融交易流水造数",
            "config": {
                "fields": [
                    {"name": "txn_id", "type": "string", "description": "交易流水号"},
                    {"name": "account_number", "type": "string", "description": "银行卡号"},
                    {"name": "txn_type", "type": "string", "description": "交易类型"},
                    {"name": "amount", "type": "decimal", "description": "交易金额"},
                    {"name": "risk_level", "type": "string", "description": "风险等级"},
                ]
            },
            "variables": [],
            "tags": ["preset", "fintech"],
        },
    ]

    inserted_tpl = 0
    for tpl in templates:
        tpl_id = "tpl-" + str(uuid.uuid4())[:8]
        try:
            conn.execute(
                """
                INSERT INTO datafactory_templates
                (tpl_id, name, description, domain, category, scenario, config,
                 variables, tags, created_by, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    tpl_id,
                    tpl["name"],
                    tpl["description"],
                    tpl["domain"],
                    tpl["category"],
                    tpl["scenario"],
                    json.dumps(tpl["config"], ensure_ascii=False),
                    json.dumps(tpl["variables"], ensure_ascii=False),
                    json.dumps(tpl["tags"], ensure_ascii=False),
                    "ai-base",
                    now,
                    now,
                ),
            )
            inserted_tpl += 1
        except Exception as e:
            print(f"[seed] 写入模板失败 {tpl['name']}: {e}")

    conn.commit()
    conn.close()
    print(f"[seed] 数据工厂演示数据写入完成：数据集 {inserted_ds} 个，模板 {inserted_tpl} 个，DB: {DB_PATH}")


if __name__ == "__main__":
    seed_datasets()
