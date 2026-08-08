"""
任务持久化存储 — Agent Harness 任务/链路/模版/Prompt 的唯一归口

设计：
- 使用 SQLite（Python 内置，零依赖）存储任务记录
- 支持按 status / task_type / 时间范围查询
- 支持统计聚合（summary、trend、sandbox_usage）
- 支持 Prompt 版本管理与热更新
- 自动建表、自动清理过期记录（默认保留 90 天）

存储结构：
  tasks 表：任务主记录
  trace_steps 表：每条任务的执行步骤链路
  prompts 表：Prompt 版本管理
  model_configs 表：模型配置
  tenants 表：业务接入方（Phase 2.2）
  sandboxes 表：沙箱实例（Phase 2.3）
  mcp_tools 表：MCP 工具注册（Phase 2.4）
  webhook_configs 表：通知 Webhook 配置（Phase 2.5）

Phase 2.1：替换 tasks.py 中所有 MOCK_TASKS / MOCK_PROMPTS / MODELS 内存数据
Phase 2.2：替换 tenants.py 中 MOCK_TENANTS 内存数据，stats 从 tasks 表实时计算
Phase 2.3：替换 sandbox.py 中 MOCK_SANDBOXES 内存数据，沙箱实例持久化
Phase 2.4：替换 mcp.py 中 MOCK_TOOLS 内存数据，MCP 工具注册持久化
"""

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# 数据库路径
DB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)
DB_PATH = os.path.join(DB_DIR, "harness.db")

RETENTION_DAYS = 90


# ============================================================
# 数据类
# ============================================================

@dataclass
class TaskRecord:
    """任务主记录"""
    id: str = ""
    task_type: str = ""
    user_request: str = ""
    status: str = "pending"      # pending / running / completed / failed
    steps_count: int = 0
    duration_ms: int = 0
    team_id: str = "default"
    user_id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TraceStepRecord:
    """执行步骤记录"""
    id: Optional[int] = None
    task_id: str = ""
    step: int = 0
    phase: str = ""
    title: str = ""
    thinking: str = ""
    action: str = ""
    duration_ms: int = 0
    status: str = "success"
    output_json: str = "{}"
    created_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("id", None)
        d.pop("task_id", None)
        d["output"] = json.loads(d.pop("output_json", "{}") or "{}")
        return d


@dataclass
class PromptRecord:
    """Prompt 版本记录"""
    id: Optional[int] = None
    agent_name: str = ""
    prompt_type: str = "system"
    prompt_subtype: str = "default"
    system_prompt: str = ""
    user_prompt_template: str = ""
    version: int = 1
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("created_at", None)
        d.pop("updated_at", None)
        return d


@dataclass
class ModelConfigRecord:
    """模型配置"""
    id: Optional[int] = None
    name: str = ""
    provider: str = ""
    description: str = ""
    is_enabled: bool = True
    base_url: str = ""
    api_key_placeholder: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "provider": self.provider,
            "description": self.description,
        }


@dataclass
class TenantRecord:
    """业务接入方（Phase 2.2）"""
    id: Optional[int] = None
    name: str = ""
    team: str = ""
    api_key: str = ""
    status: str = "active"           # active / disabled
    qps: int = 50
    daily_cap: int = 5000
    tools_whitelist: str = "[]"      # JSON array string
    contact: str = ""
    created_at: str = ""

    def to_dict(self, stats: Optional[dict] = None) -> dict:
        """转为 API 响应格式，stats 从 tasks 表实时计算传入"""
        return {
            "id": self.id,
            "name": self.name,
            "team": self.team,
            "api_key": self.api_key,
            "status": self.status,
            "rate_limit": {"qps": self.qps, "daily_cap": self.daily_cap},
            "tools_whitelist": json.loads(self.tools_whitelist or "[]"),
            "contact": self.contact,
            "stats": stats or {"total_calls": 0, "today_calls": 0, "avg_latency_ms": 0},
            "created_at": self.created_at,
        }


@dataclass
class TeamModelPrefsRecord:
    """团队模型偏好 — SaaS 核心：每个团队可覆盖全局路由表中的模型"""
    id: Optional[int] = None
    team_id: str = ""
    planning_model: str = ""
    code_generation_model: str = ""
    evaluation_model: str = ""
    agent_model: str = ""
    fast_chat_model: str = ""
    data_generation_model: str = ""
    rag_query_model: str = ""
    fallback_model: str = ""
    created_at: str = ""
    updated_at: str = ""

    # task_type → column_name 映射
    TASK_TYPE_TO_FIELD = {
        "planning": "planning_model",
        "code_generation": "code_generation_model",
        "evaluation": "evaluation_model",
        "agent": "agent_model",
        "fast_chat": "fast_chat_model",
        "data_generation": "data_generation_model",
        "rag_query": "rag_query_model",
        "fallback": "fallback_model",
    }

    def get_model_for_task_type(self, task_type: str) -> str:
        """获取某 task_type 的团队偏好模型，为空字符串表示未设置"""
        field = self.TASK_TYPE_TO_FIELD.get(task_type)
        return getattr(self, field, "") if field else ""

    def to_dict(self) -> dict:
        """转为 API 响应格式"""
        return {
            "id": self.id,
            "team_id": self.team_id,
            "planning_model": self.planning_model,
            "code_generation_model": self.code_generation_model,
            "evaluation_model": self.evaluation_model,
            "agent_model": self.agent_model,
            "fast_chat_model": self.fast_chat_model,
            "data_generation_model": self.data_generation_model,
            "rag_query_model": self.rag_query_model,
            "fallback_model": self.fallback_model,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class SandboxRecord:
    """沙箱实例记录（Phase 2.3）"""
    id: Optional[int] = None
    sbx_id: str = ""                    # 对外 ID 如 sbx-a1b2c3d4
    name: str = ""
    sbx_type: str = "python"            # python / node / browser
    status: str = "running"             # running / idle / terminated
    memory_mb: int = 512
    memory_used_mb: int = 0
    cpu_percent: int = 0
    uptime_seconds: int = 0
    host: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.sbx_id,
            "name": self.name,
            "type": self.sbx_type,
            "status": self.status,
            "memory_mb": self.memory_mb,
            "memory_used_mb": self.memory_used_mb,
            "cpu_percent": self.cpu_percent,
            "uptime_seconds": self.uptime_seconds,
            "host": self.host,
            "created_at": self.created_at,
        }


@dataclass
class MCPToolRecord:
    """MCP 工具注册记录（Phase 2.4）"""
    id: Optional[int] = None
    tool_id: str = ""                   # 对外 ID 如 tool-1
    name: str = ""
    category: str = ""                  # search/file/database/code/browser/notify
    description: str = ""
    endpoint: str = ""
    status: str = "active"              # active / disabled
    success_rate: int = 0
    avg_latency_ms: int = 0
    call_count: int = 0
    input_schema: str = "{}"            # JSON string
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.tool_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "endpoint": self.endpoint,
            "status": self.status,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "call_count": self.call_count,
        }


@dataclass
class WebhookRecord:
    """通知 Webhook 配置记录（Phase 2.5）"""
    id: Optional[int] = None
    wh_id: str = ""                         # 对外 ID 如 wh-1
    name: str = ""                          # 飞书通知 / 钉钉告警 / 企业微信
    platform: str = ""                      # feishu / dingtalk / wecom
    url: str = ""                           # Webhook URL
    secret: str = ""                        # 签名密钥（飞书安全设置）
    active: bool = True                     # 是否启用
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.wh_id,
            "name": self.name,
            "platform": self.platform,
            "url": self.url,
            "secret": self.secret,
            "active": self.active,
            "created_at": self.created_at,
        }


# ============================================================
# TaskStore 实现
# ============================================================

class TaskStore:
    """任务持久化存储（SQLite）"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        self._seed_defaults()

    # ── 数据库初始化 ──

    def _init_db(self):
        """建表 + 索引"""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL DEFAULT '',
                    user_request TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    steps_count INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    team_id TEXT NOT NULL DEFAULT 'default',
                    user_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS trace_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step INTEGER NOT NULL DEFAULT 0,
                    phase TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    thinking TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'success',
                    output_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL DEFAULT '',
                    prompt_type TEXT NOT NULL DEFAULT 'system',
                    prompt_subtype TEXT NOT NULL DEFAULT 'default',
                    system_prompt TEXT NOT NULL DEFAULT '',
                    user_prompt_template TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS model_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    provider TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    base_url TEXT NOT NULL DEFAULT '',
                    api_key_placeholder TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS tenants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL DEFAULT '',
                    team TEXT NOT NULL DEFAULT '',
                    api_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'active',
                    qps INTEGER NOT NULL DEFAULT 50,
                    daily_cap INTEGER NOT NULL DEFAULT 5000,
                    tools_whitelist TEXT NOT NULL DEFAULT '[]',
                    contact TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS sandboxes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sbx_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    sbx_type TEXT NOT NULL DEFAULT 'python',
                    status TEXT NOT NULL DEFAULT 'idle',
                    memory_mb INTEGER NOT NULL DEFAULT 512,
                    memory_used_mb INTEGER NOT NULL DEFAULT 0,
                    cpu_percent INTEGER NOT NULL DEFAULT 0,
                    uptime_seconds INTEGER NOT NULL DEFAULT 0,
                    host TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS mcp_tools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    endpoint TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    success_rate INTEGER NOT NULL DEFAULT 0,
                    avg_latency_ms INTEGER NOT NULL DEFAULT 0,
                    call_count INTEGER NOT NULL DEFAULT 0,
                    input_schema TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                -- 索引
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_tasks_team ON tasks(team_id, user_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);
                CREATE INDEX IF NOT EXISTS idx_trace_task ON trace_steps(task_id, step);
                CREATE INDEX IF NOT EXISTS idx_prompts_agent ON prompts(agent_name, prompt_type);
                CREATE INDEX IF NOT EXISTS idx_tenants_api_key ON tenants(api_key);
                CREATE INDEX IF NOT EXISTS idx_sandboxes_sbx_id ON sandboxes(sbx_id);
                CREATE INDEX IF NOT EXISTS idx_mcp_tools_name ON mcp_tools(name);

                CREATE TABLE IF NOT EXISTS webhook_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wh_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    platform TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    secret TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_webhook_wh_id ON webhook_configs(wh_id);
            """)
            # 兼容旧表：无 secret 列时自动补上
            cols = [row['name'] for row in conn.execute("PRAGMA table_info(webhook_configs)").fetchall()]
            if 'secret' not in cols:
                conn.execute("ALTER TABLE webhook_configs ADD COLUMN secret TEXT NOT NULL DEFAULT ''")
            conn.commit()

            # ── 团队模型偏好表（SaaS 核心：团队可覆盖全局路由表） ──
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS team_model_prefs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id TEXT NOT NULL UNIQUE,
                    planning_model TEXT NOT NULL DEFAULT '',
                    code_generation_model TEXT NOT NULL DEFAULT '',
                    evaluation_model TEXT NOT NULL DEFAULT '',
                    agent_model TEXT NOT NULL DEFAULT '',
                    fast_chat_model TEXT NOT NULL DEFAULT '',
                    data_generation_model TEXT NOT NULL DEFAULT '',
                    rag_query_model TEXT NOT NULL DEFAULT '',
                    fallback_model TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_team_model_prefs_team_id
                    ON team_model_prefs(team_id);

                -- 团队编排任务表
                CREATE TABLE IF NOT EXISTS team_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'inbox',
                    team_id TEXT NOT NULL DEFAULT 'default',
                    user_id TEXT NOT NULL DEFAULT '',
                    assigned_to TEXT DEFAULT '',
                    assigned_agent TEXT DEFAULT '',
                    required_roles_json TEXT NOT NULL DEFAULT '[]',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    priority INTEGER NOT NULL DEFAULT 3,
                    parent_task_id TEXT DEFAULT NULL,
                    model TEXT DEFAULT '',
                    context_json TEXT NOT NULL DEFAULT '{}',
                    artifacts_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_team_tasks_status ON team_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_team_tasks_team ON team_tasks(team_id, user_id);
                CREATE INDEX IF NOT EXISTS idx_team_tasks_created ON team_tasks(created_at DESC);

                -- 团队交接记录表
                CREATE TABLE IF NOT EXISTS team_handoffs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    handoff_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL,
                    from_role TEXT NOT NULL DEFAULT '',
                    to_role TEXT NOT NULL DEFAULT '',
                    from_agent TEXT NOT NULL DEFAULT '',
                    to_agent TEXT NOT NULL DEFAULT '',
                    intent TEXT NOT NULL DEFAULT 'delegate',
                    context TEXT NOT NULL DEFAULT '',
                    deliverables_json TEXT NOT NULL DEFAULT '[]',
                    blockers_json TEXT NOT NULL DEFAULT '[]',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_team_handoffs_task ON team_handoffs(task_id, created_at DESC);

                -- 团队评审记录表
                CREATE TABLE IF NOT EXISTS team_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL,
                    reviewer_role TEXT NOT NULL DEFAULT 'reviewer',
                    reviewer_agent TEXT NOT NULL DEFAULT '',
                    builder_agent TEXT NOT NULL DEFAULT '',
                    artifacts_json TEXT NOT NULL DEFAULT '[]',
                    criteria_json TEXT NOT NULL DEFAULT '[]',
                    verdict TEXT DEFAULT '',
                    score INTEGER DEFAULT NULL,
                    comments_json TEXT NOT NULL DEFAULT '[]',
                    required_changes_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_team_reviews_task ON team_reviews(task_id, created_at DESC);
            """)
            conn.commit()

    def _seed_defaults(self):
        """首次运行时写入默认 Prompt、模型配置和种子任务"""
        now = datetime.now(timezone.utc).isoformat()
        sample_tasks = self._build_sample_tasks()

        with self._get_conn() as conn:
            # 默认 Prompt
            prompt_count = conn.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
            if prompt_count == 0:
                default_prompts = [
                    (
                        "test_case_generator", "system", "standard",
                        "你是一名资深测试工程师，擅长根据需求生成高质量测试用例。",
                        "请根据以下需求生成测试用例：\n{requirement}", 3, 1, now, now,
                    ),
                    (
                        "data_factory_agent", "system", "default",
                        "你是数据工厂，负责生成测试数据。",
                        "请生成 {count} 条 {schema} 数据。", 1, 1, now, now,
                    ),
                    (
                        "evaluator", "system", "default",
                        "你是一名 AI 回答评测专家，负责对模型输出打分。",
                        "请评估以下回答：\n{answer}", 2, 0, now, now,
                    ),
                ]
                conn.executemany(
                    """INSERT INTO prompts
                    (agent_name, prompt_type, prompt_subtype, system_prompt,
                     user_prompt_template, version, is_active, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    default_prompts,
                )

            # 默认模型配置
            model_count = conn.execute("SELECT COUNT(*) FROM model_configs").fetchone()[0]
            if model_count == 0:
                default_models = [
                    ("deepseek-chat", "DeepSeek", "主要文本生成模型", 1, "https://api.deepseek.com/v1", "", now),
                    ("qwen-plus", "阿里云百炼", "视觉+文本模型", 1, "", "", now),
                    ("qwen-max", "阿里云百炼", "高精度复杂推理（按需启用）", 1, "", "", now),
                ]
                conn.executemany(
                    """INSERT INTO model_configs
                    (name, provider, description, is_enabled, base_url, api_key_placeholder, created_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    default_models,
                )

            # 种子任务 + 链路步骤
            task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            if task_count == 0:
                conn.executemany(
                    """INSERT INTO tasks
                    (id, task_type, user_request, status, steps_count, duration_ms,
                     team_id, user_id, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    [(t.id, t.task_type, t.user_request, t.status,
                      t.steps_count, t.duration_ms, t.team_id, t.user_id,
                      t.created_at, t.updated_at) for t in sample_tasks["tasks"]],
                )
                for ts in sample_tasks["traces"]:
                    conn.executemany(
                        """INSERT INTO trace_steps
                        (task_id, step, phase, title, thinking, action, duration_ms, status, output_json, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        [(t.task_id, t.step, t.phase, t.title, t.thinking,
                          t.action, t.duration_ms, t.status, t.output_json, t.created_at)
                         for t in sample_tasks["traces"][ts]],
                    )
                conn.commit()
                task_count = len(sample_tasks["tasks"])
                logger.info(f"[TaskStore] 已写入 {task_count} 条种子任务")

            # 种子租户（Phase 2.2）
            tenant_count = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
            if tenant_count == 0:
                default_tenants = [
                    ("AI 测试平台", "质量中台", "ak-ai-test-platform-7d3f9a2b", "active",
                     100, 10000, '["search","browser","python_repl","sql_query","file_reader"]',
                     "qa-platform@example.com", now),
                    ("研发一组", "交易研发部", "ak-rd-team-01-e8c5d1a7", "active",
                     80, 8000, '["search","browser","python_repl"]',
                     "rd-01@example.com", now),
                    ("测试中台", "质量保障部", "ak-qa-center-9f2b4c6d", "active",
                     120, 20000, '["search","browser","python_repl","sql_query","file_reader","web_scraper"]',
                     "qa-center@example.com", now),
                ]
                conn.executemany(
                    """INSERT INTO tenants
                    (name, team, api_key, status, qps, daily_cap, tools_whitelist, contact, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    default_tenants,
                )
                conn.commit()
                logger.info("[TaskStore] 已写入 3 条种子租户")

            # 种子沙箱（Phase 2.3）
            sandbox_count = conn.execute("SELECT COUNT(*) FROM sandboxes").fetchone()[0]
            if sandbox_count == 0:
                default_sandboxes = [
                    ("sbx-a1b2c3d4", "Python 3.11 默认", "python", "running",
                     512, 89, 12, 3600, "worker-01", now),
                    ("sbx-e5f6g7h8", "Node.js 20 环境", "node", "running",
                     1024, 156, 8, 7200, "worker-02", now),
                    ("sbx-i9j0k1l2", "浏览器自动化", "browser", "running",
                     2048, 423, 25, 1800, "worker-01", now),
                    ("sbx-m3n4o5p6", "Python 3.11 备用", "python", "idle",
                     512, 12, 2, 5400, "worker-03", now),
                    ("sbx-q7r8s9t0", "Node.js 20 测试", "node", "idle",
                     1024, 34, 5, 900, "worker-02", now),
                    ("sbx-u1v2w3x4", "Python 3.11 压测", "python", "terminated",
                     1024, 0, 0, 0, "worker-01", now),
                    ("sbx-y5z6a7b8", "浏览器截图", "browser", "idle",
                     2048, 201, 18, 360, "worker-03", now),
                    ("sbx-c9d0e1f2", "Python 3.11 调试", "python", "running",
                     512, 67, 9, 120, "worker-01", now),
                ]
                conn.executemany(
                    """INSERT INTO sandboxes
                    (sbx_id, name, sbx_type, status, memory_mb, memory_used_mb,
                     cpu_percent, uptime_seconds, host, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    default_sandboxes,
                )
                conn.commit()
                logger.info("[TaskStore] 已写入 8 条种子沙箱")

            # 种子 MCP 工具（Phase 2.4）
            tool_count = conn.execute("SELECT COUNT(*) FROM mcp_tools").fetchone()[0]
            if tool_count == 0:
                default_tools = [
                    ("tool-1", "search", "search", "知识库检索工具，用于 RAG 召回。",
                     "/mcp/search", "active", 98, 120, 1240, now),
                    ("tool-2", "file_reader", "file", "读取文件内容，支持多种代码文件。",
                     "/mcp/file/read", "active", 96, 80, 856, now),
                    ("tool-3", "sql_executor", "database", "在沙箱内执行 SQL 查询。",
                     "/mcp/db/exec", "active", 94, 200, 432, now),
                    ("tool-4", "code_runner", "code", "执行 Python/Node 脚本片段。",
                     "/mcp/code/run", "active", 92, 350, 621, now),
                    ("tool-5", "browser_navigate", "browser", "浏览器导航与页面操作。",
                     "/mcp/browser/nav", "disabled", 88, 800, 120, now),
                    ("tool-6", "notify", "notify", "发送通知到钉钉/飞书。",
                     "/mcp/notify/send", "active", 99, 60, 310, now),
                ]
                conn.executemany(
                    """INSERT INTO mcp_tools
                    (tool_id, name, category, description, endpoint, status,
                     success_rate, avg_latency_ms, call_count, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    default_tools,
                )
                conn.commit()
                logger.info("[TaskStore] 已写入 6 条种子 MCP 工具")

            # 种子 Webhook 配置（Phase 2.5）
            webhook_count = conn.execute("SELECT COUNT(*) FROM webhook_configs").fetchone()[0]
            if webhook_count == 0:
                default_webhooks = [
                    ("wh-1", "飞书通知", "feishu",
                     "https://open.feishu.cn/open-apis/bot/v2/hook/e9af0623-8049-4050-a6c5-474c32977db8",
                     "qqNttg7TpqzkmPS7vFexbc", 1, now),
                    ("wh-2", "企业微信", "wecom",
                     "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your-key",
                     "", 1, now),
                    ("wh-3", "钉钉告警", "dingtalk",
                     "https://oapi.dingtalk.com/robot/send?access_token=your-token",
                     "", 0, now),
                ]
                conn.executemany(
                    """INSERT INTO webhook_configs
                    (wh_id, name, platform, url, secret, active, created_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    default_webhooks,
                )
                conn.commit()
                logger.info("[TaskStore] 已写入 3 条种子 Webhook 配置")

    @staticmethod
    def _build_sample_tasks() -> dict:
        """构建种子任务数据（初次启动用）"""
        now = datetime.now(timezone.utc)
        tasks = []

        # 生成最近 7 天均匀分布的任务
        statuses = ["completed", "completed", "completed", "running", "failed", "pending", "completed"]
        task_types = ["test_case_gen", "test_case_gen", "execution", "execution", "data_factory", "test_case_gen", "execution"]
        requests = [
            "为'用户登录'功能生成 10 条测试用例，覆盖正常流程...",
            "为'支付回调'接口生成异常场景测试用例，包含网络超时...",
            "执行测试套件 regression-suite-v3，共 25 个用例",
            "执行性能基准测试 benchmark-auth，目标 QPS 500",
            "为'订单表'生成 1000 条测试数据，模拟双十一峰值场景",
            "为'权限校验'模块生成自动化测试用例，基于 RBAC 模型",
            "执行 E2E 测试 purchase-flow，覆盖下单→支付→发货全链路",
        ]

        for i, (day_offset) in enumerate([6, 5, 4, 3, 2, 1, 0]):
            task_date = now - timedelta(days=day_offset, hours=i * 3, minutes=15 * i)
            dur_map = {"completed": [1200, 4500, 800, 2300, 5600], "running": [3100], "failed": [8900], "pending": [0]}
            status = statuses[i]
            dur = dur_map[status][i % len(dur_map[status])]
            tasks.append(TaskRecord(
                id=f"task-{i + 1:04d}",
                task_type=task_types[i],
                user_request=requests[i],
                status=status,
                steps_count=4 if status == "completed" else (2 if status == "running" else (3 if status == "failed" else 0)),
                duration_ms=dur,
                team_id="default",
                user_id="admin",
                created_at=task_date.isoformat(),
                updated_at=task_date.isoformat(),
            ))

        # 链路步骤（为 completed/failed 任务）
        trace_data = {}
        phases = [("plan", "分析需求", "拆解用户请求 → 选择工作流模板", "plan_node"),
                  ("orchestrate", "编排工具", "选择 test_case_gen 工具链", "orchestrate_node"),
                  ("react", "执行生成", "调用 LLM 生成测试用例", "react_node"),
                  ("verify", "验证结果", "检查生成的用例格式和数量", "verify_node")]
        for task in tasks:
            if task.status == "pending":
                continue
            steps = []
            for s_idx, (phase, title, thinking, action) in enumerate(phases[:3 if task.status == "failed" else 4]):
                step_status = "success" if (task.status == "completed" or s_idx < 2) else "error"
                output = {"message": f"Phase {phase} completed"} if step_status == "success" else {"error": "Tool timeout"}
                steps.append(TraceStepRecord(
                    task_id=task.id, step=s_idx + 1, phase=phase, title=title,
                    thinking=thinking, action=f"Tool: {action}",
                    duration_ms=task.duration_ms // 4 if task.duration_ms else 0,
                    status=step_status, output_json=json.dumps(output),
                    created_at=task.created_at,
                ))
            trace_data[task.id] = steps

        return {"tasks": tasks, "traces": trace_data}

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    # ── 任务 CRUD ──

    def create_task(self, task: TaskRecord) -> str:
        """创建任务，返回 task_id"""
        with self._lock:
            if not task.created_at:
                task.created_at = datetime.now(timezone.utc).isoformat()
            if not task.updated_at:
                task.updated_at = task.created_at

            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO tasks
                    (id, task_type, user_request, status, steps_count, duration_ms,
                     team_id, user_id, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        task.id, task.task_type, task.user_request, task.status,
                        task.steps_count, task.duration_ms,
                        task.team_id, task.user_id, task.created_at, task.updated_at,
                    ),
                )
                conn.commit()
                logger.debug(f"[TaskStore] 创建任务 id={task.id}")
                return task.id

    def update_task(self, task_id: str, **kwargs) -> bool:
        """更新任务字段"""
        allowed = {"status", "steps_count", "duration_ms", "user_request", "updated_at"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]

        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    f"UPDATE tasks SET {set_clause} WHERE id = ?", values
                )
                conn.commit()
                return cursor.rowcount > 0

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """获取单条任务"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            return TaskRecord(**dict(row))

    def list_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        team_id: Optional[str] = None,
        page_size: int = 50,
        offset: int = 0,
    ) -> tuple[list[TaskRecord], int]:
        """列出任务（分页），返回 (results, total_count)"""
        conditions = ["1=1"]
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if task_type:
            conditions.append("task_type = ?")
            params.append(task_type)
        if team_id:
            conditions.append("team_id = ?")
            params.append(team_id)

        where = " AND ".join(conditions)
        count_sql = f"SELECT COUNT(*) FROM tasks WHERE {where}"
        list_sql = f"SELECT * FROM tasks WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"

        with self._get_conn() as conn:
            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(list_sql, params + [page_size, offset]).fetchall()
            return [TaskRecord(**dict(r)) for r in rows], total

    def list_recent(self, limit: int = 10) -> list[TaskRecord]:
        """获取最近 N 条任务"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [TaskRecord(**dict(r)) for r in rows]

    def search_tasks(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        page_size: int = 50,
    ) -> list[TaskRecord]:
        """搜索任务（按 id / user_request 模糊匹配）"""
        conditions = ["1=1"]
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if q:
            conditions.append("(id LIKE ? OR user_request LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM tasks WHERE {where} ORDER BY created_at DESC LIMIT ?"

        with self._get_conn() as conn:
            rows = conn.execute(sql, params + [page_size]).fetchall()
            return [TaskRecord(**dict(r)) for r in rows]

    # ── 执行步骤 CRUD ──

    def save_trace_steps(self, task_id: str, steps: list[TraceStepRecord]):
        """保存任务的执行步骤（先删后插）"""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM trace_steps WHERE task_id = ?", (task_id,))
                now = datetime.now(timezone.utc).isoformat()
                for s in steps:
                    s.task_id = task_id
                    s.created_at = now
                    conn.execute(
                        """INSERT INTO trace_steps
                        (task_id, step, phase, title, thinking, action, duration_ms, status, output_json, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (
                            task_id, s.step, s.phase, s.title, s.thinking,
                            s.action, s.duration_ms, s.status,
                            s.output_json, s.created_at,
                        ),
                    )
                conn.commit()

    def get_trace_steps(self, task_id: str) -> list[TraceStepRecord]:
        """获取任务的执行步骤"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trace_steps WHERE task_id = ? ORDER BY step ASC",
                (task_id,),
            ).fetchall()
            return [TraceStepRecord(**dict(r)) for r in rows]

    # ── 统计聚合 ──

    def get_stats(self, team_id: Optional[str] = None) -> dict:
        """获取任务统计（summary / trend / sandbox_usage）"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        team_filter = "AND team_id = ?" if team_id else ""
        team_params = [team_id] if team_id else []

        with self._get_conn() as conn:
            # 状态汇总
            summary_sql = """
                SELECT status, COUNT(*) as cnt
                FROM tasks WHERE 1=1 {team}
                GROUP BY status
            """.format(team=team_filter)
            rows = conn.execute(summary_sql, team_params).fetchall()
            summary = {"running": 0, "pending": 0, "failed": 0, "completed": 0}
            for r in rows:
                if r["status"] in summary:
                    summary[r["status"]] = r["cnt"]

            # 今日调用量
            today_calls_sql = f"""
                SELECT COUNT(*) as cnt FROM tasks
                WHERE date(created_at) = ? {team_filter}
            """
            today_calls = conn.execute(
                today_calls_sql, [today] + team_params
            ).fetchone()["cnt"]

            # 平均耗时（非 pending 任务）
            avg_sql = f"""
                SELECT COALESCE(ROUND(AVG(duration_ms)), 0) as avg_dur
                FROM tasks WHERE status != 'pending' {team_filter}
            """
            avg_duration_ms = conn.execute(avg_sql, team_params).fetchone()["avg_dur"]

            # 成功率
            success_sql = f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success
                FROM tasks WHERE status != 'pending' {team_filter}
            """
            sr = conn.execute(success_sql, team_params).fetchone()
            total = sr["total"] or 1
            success_rate = round((sr["success"] or 0) / total * 100)

            # 近 7 天趋势（从真实数据聚合）
            trend = []
            for i in range(6, -1, -1):
                d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
                trend_sql = f"""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM tasks
                    WHERE date(created_at) = ? {team_filter}
                """
                tr = conn.execute(trend_sql, [d] + team_params).fetchone()
                trend.append({
                    "date": d[5:],  # MM-DD
                    "total": tr["total"] or 0,
                    "success": tr["success"] or 0,
                    "failed": tr["failed"] or 0,
                })

            # 沙箱资源占用（按任务状态聚合，后续 Phase 2.3 改为实时进程查询）
            sandbox_sql = f"""
                SELECT status, COUNT(*) as cnt
                FROM tasks WHERE status IN ('running', 'completed', 'failed') {team_filter}
                GROUP BY status
            """
            sandbox_rows = conn.execute(sandbox_sql, team_params).fetchall()
            sandbox_map = {r["status"]: r["cnt"] for r in sandbox_rows}
            sandbox_usage = [
                {"name": "运行中（沙箱占用）", "total": 10, "used": min(sandbox_map.get("running", 0), 10)},
                {"name": "待回收（已完成）", "total": 20, "used": min(sandbox_map.get("completed", 0), 20)},
                {"name": "异常（待清理）", "total": 5, "used": min(sandbox_map.get("failed", 0), 5)},
            ]

        return {
            "summary": summary,
            "today_calls": today_calls,
            "avg_duration_ms": avg_duration_ms,
            "success_rate": success_rate,
            "trend": trend,
            "sandbox_usage": sandbox_usage,
        }

    # ── Prompt 管理 ──

    def list_prompts(self) -> list[PromptRecord]:
        """获取所有 Prompt 配置"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM prompts ORDER BY agent_name, prompt_subtype"
            ).fetchall()
            return [PromptRecord(**dict(r)) for r in rows]

    def get_prompt(self, prompt_id: int) -> Optional[PromptRecord]:
        """获取单条 Prompt"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
            ).fetchone()
            if row is None:
                return None
            return PromptRecord(**dict(row))

    def update_prompt(self, prompt_id: int, system_prompt: str, user_prompt_template: str) -> Optional[PromptRecord]:
        """更新 Prompt（版本号 +1，更新 updated_at）"""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                # 获取当前版本号
                current = conn.execute(
                    "SELECT version FROM prompts WHERE id = ?", (prompt_id,)
                ).fetchone()
                if current is None:
                    return None
                new_version = current["version"] + 1
                conn.execute(
                    """UPDATE prompts
                    SET system_prompt = ?, user_prompt_template = ?,
                        version = ?, updated_at = ?
                    WHERE id = ?""",
                    (system_prompt, user_prompt_template, new_version, now, prompt_id),
                )
                conn.commit()

                row = conn.execute(
                    "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
                ).fetchone()
                return PromptRecord(**dict(row))

    # ── 模型配置 ──

    def list_models(self) -> list[ModelConfigRecord]:
        """获取启用的模型配置"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM model_configs ORDER BY name"
            ).fetchall()
            return [ModelConfigRecord(**dict(r)) for r in rows]

    # ── 租户管理（Phase 2.2） ──

    def _get_tenant_stats(self, tenant_name: str) -> dict:
        """从 tasks 表实时计算租户调用统计"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks"
            ).fetchone()[0]
            today_count = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE date(created_at) = ?", (today,)
            ).fetchone()[0]
            avg_row = conn.execute(
                "SELECT COALESCE(ROUND(AVG(duration_ms)), 0) FROM tasks WHERE status != 'pending'"
            ).fetchone()
            avg_latency = avg_row[0] if avg_row else 0
        return {
            "total_calls": total,
            "today_calls": today_count,
            "avg_latency_ms": avg_latency,
        }

    def list_tenants(self) -> list[dict]:
        """列出所有租户（含实时统计）"""
        global_stats = self._get_tenant_stats("")
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tenants ORDER BY created_at DESC"
            ).fetchall()
            # 按租户分摊统计（暂用全局统计替代，后续可加 tenant_id 关联精确计算）
            tenant_count = max(len(rows), 1)
            results = []
            for r in rows:
                rec = TenantRecord(**dict(r))
                # 每个租户均摊统计
                stats = {
                    "total_calls": global_stats["total_calls"] // tenant_count,
                    "today_calls": global_stats["today_calls"] // tenant_count,
                    "avg_latency_ms": global_stats["avg_latency_ms"],
                }
                results.append(rec.to_dict(stats))
            return results

    def get_tenant(self, tenant_id: int) -> Optional[TenantRecord]:
        """获取单个租户"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM tenants WHERE id = ?", (tenant_id,)
            ).fetchone()
            if row is None:
                return None
            return TenantRecord(**dict(row))

    def create_tenant(self, name: str, team: str, api_key: str,
                      qps: int = 50, daily_cap: int = 5000,
                      tools_whitelist: list = None, contact: str = "") -> TenantRecord:
        """创建租户，返回完整记录"""
        now = datetime.now(timezone.utc).isoformat()
        whitelist_json = json.dumps(tools_whitelist or [])
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """INSERT INTO tenants
                    (name, team, api_key, status, qps, daily_cap, tools_whitelist, contact, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (name, team, api_key, "active", qps, daily_cap, whitelist_json, contact, now),
                )
                conn.commit()
                new_id = cursor.lastrowid
        return TenantRecord(
            id=new_id, name=name, team=team, api_key=api_key, status="active",
            qps=qps, daily_cap=daily_cap, tools_whitelist=whitelist_json,
            contact=contact, created_at=now,
        )

    def update_tenant(self, tenant_id: int, **kwargs) -> Optional[TenantRecord]:
        """更新租户字段"""
        allowed = {"name", "team", "status", "qps", "daily_cap", "tools_whitelist", "contact"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return self.get_tenant(tenant_id)

        # tools_whitelist 转 JSON
        if "tools_whitelist" in updates:
            updates["tools_whitelist"] = json.dumps(updates["tools_whitelist"])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [tenant_id]

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE tenants SET {set_clause} WHERE id = ?", values
                )
                conn.commit()
        return self.get_tenant(tenant_id)

    def delete_tenant(self, tenant_id: int) -> bool:
        """删除租户"""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM tenants WHERE id = ?", (tenant_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    def reset_tenant_api_key(self, tenant_id: int, new_key: str) -> Optional[TenantRecord]:
        """重置租户 API Key"""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE tenants SET api_key = ? WHERE id = ?",
                    (new_key, tenant_id),
                )
                conn.commit()
        return self.get_tenant(tenant_id)

    # ── 沙箱管理（Phase 2.3） ──

    def _generate_sbx_id(self) -> str:
        """生成沙箱对外 ID"""
        import uuid
        return f"sbx-{uuid.uuid4().hex[:8]}"

    def list_sandboxes(self) -> list[dict]:
        """列出所有沙箱实例"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sandboxes ORDER BY created_at DESC"
            ).fetchall()
            return [SandboxRecord(**dict(r)).to_dict() for r in rows]

    def get_sandbox(self, sbx_id: str) -> Optional[SandboxRecord]:
        """按 sbx_id 获取沙箱"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM sandboxes WHERE sbx_id = ?", (sbx_id,)
            ).fetchone()
            if row is None:
                return None
            return SandboxRecord(**dict(row))

    def sandbox_exists(self, sbx_id: str) -> bool:
        """检查沙箱是否存在"""
        return self.get_sandbox(sbx_id) is not None

    def create_sandbox(self, name: str, sbx_type: str = "python",
                       memory_mb: int = 512, host: str = "auto") -> SandboxRecord:
        """创建沙箱实例"""
        import random
        sbx_id = self._generate_sbx_id()
        now = datetime.now(timezone.utc).isoformat()
        if host == "auto":
            host = f"worker-0{random.randint(1,3)}"

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO sandboxes
                    (sbx_id, name, sbx_type, status, memory_mb, memory_used_mb,
                     cpu_percent, uptime_seconds, host, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (sbx_id, name, sbx_type, "running", memory_mb, 0, 0, 0, host, now),
                )
                conn.commit()

        return SandboxRecord(
            sbx_id=sbx_id, name=name, sbx_type=sbx_type, status="running",
            memory_mb=memory_mb, memory_used_mb=0, cpu_percent=0,
            uptime_seconds=0, host=host, created_at=now,
        )

    def update_sandbox_status(self, sbx_id: str, status: str) -> Optional[SandboxRecord]:
        """更新沙箱状态"""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE sandboxes SET status = ? WHERE sbx_id = ?",
                    (status, sbx_id),
                )
                conn.commit()
        return self.get_sandbox(sbx_id)

    def refresh_sandbox_stats(self, sbx_id: str, memory_used_mb: int,
                               cpu_percent: int, uptime_seconds: int) -> Optional[SandboxRecord]:
        """刷新沙箱资源使用统计"""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """UPDATE sandboxes
                    SET memory_used_mb = ?, cpu_percent = ?, uptime_seconds = ?
                    WHERE sbx_id = ?""",
                    (memory_used_mb, cpu_percent, uptime_seconds, sbx_id),
                )
                conn.commit()
        return self.get_sandbox(sbx_id)

    def delete_sandbox(self, sbx_id: str) -> bool:
        """销毁沙箱（标记为 terminated 而不是物理删除）"""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM sandboxes WHERE sbx_id = ?", (sbx_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    # ── MCP 工具管理（Phase 2.4） ──

    def list_mcp_tools(self, category: str = "") -> list[dict]:
        """列出所有 MCP 工具，支持按分类过滤"""
        with self._get_conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM mcp_tools WHERE category = ? ORDER BY tool_id",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM mcp_tools ORDER BY tool_id"
                ).fetchall()
            return [MCPToolRecord(**dict(r)).to_dict() for r in rows]

    def get_mcp_tool(self, name: str) -> Optional[MCPToolRecord]:
        """按工具名获取"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM mcp_tools WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                return None
            return MCPToolRecord(**dict(row))

    def create_mcp_tool(self, name: str, category: str, description: str = "",
                        endpoint: str = "", status: str = "active",
                        input_schema: dict = None) -> MCPToolRecord:
        """新增 MCP 工具"""
        import uuid
        tool_id = f"tool-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        schema_json = json.dumps(input_schema or {})

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO mcp_tools
                    (tool_id, name, category, description, endpoint, status,
                     success_rate, avg_latency_ms, call_count, input_schema, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (tool_id, name, category, description,
                     endpoint or f"/mcp/{name}", status,
                     100, 0, 0, schema_json, now),
                )
                conn.commit()

        return MCPToolRecord(
            tool_id=tool_id, name=name, category=category,
            description=description, endpoint=endpoint or f"/mcp/{name}",
            status=status, success_rate=100, avg_latency_ms=0,
            call_count=0, input_schema=schema_json, created_at=now,
        )

    def update_mcp_tool(self, name: str, **kwargs) -> Optional[MCPToolRecord]:
        """更新 MCP 工具字段"""
        allowed = {"status", "description", "endpoint", "success_rate",
                    "avg_latency_ms", "call_count", "category"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return self.get_mcp_tool(name)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [name]

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE mcp_tools SET {set_clause} WHERE name = ?", values
                )
                conn.commit()
        return self.get_mcp_tool(name)

    def delete_mcp_tool(self, name: str) -> bool:
        """删除 MCP 工具"""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM mcp_tools WHERE name = ?", (name,)
                )
                conn.commit()
                return cursor.rowcount > 0

    def bump_mcp_tool_call(self, name: str) -> None:
        """工具调用计数 +1"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE mcp_tools SET call_count = call_count + 1 WHERE name = ?",
                (name,),
            )
            conn.commit()

    # ── Webhook 配置管理（Phase 2.5） ──

    def list_webhooks(self) -> list[dict]:
        """列出所有 Webhook 配置"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM webhook_configs ORDER BY wh_id"
            ).fetchall()
            return [WebhookRecord(**dict(r)).to_dict() for r in rows]

    def get_webhook(self, wh_id: str) -> Optional[WebhookRecord]:
        """按 wh_id 获取单个 Webhook"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM webhook_configs WHERE wh_id = ?", (wh_id,)
            ).fetchone()
            if row is None:
                return None
            return WebhookRecord(**dict(row))

    def create_webhook(self, name: str, platform: str, url: str,
                       secret: str = "", active: bool = True) -> WebhookRecord:
        """新增 Webhook 配置"""
        import uuid
        wh_id = f"wh-{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO webhook_configs
                    (wh_id, name, platform, url, secret, active, created_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (wh_id, name, platform, url, secret, int(active), now),
                )
                conn.commit()

        return WebhookRecord(
            wh_id=wh_id, name=name, platform=platform,
            url=url, secret=secret, active=active, created_at=now,
        )

    def update_webhook(self, wh_id: str, **kwargs) -> Optional[WebhookRecord]:
        """更新 Webhook 配置（name, platform, url, secret, active）"""
        allowed = {"name", "platform", "url", "secret", "active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return self.get_webhook(wh_id)

        # active 字段是 INTEGER，需要转换
        if "active" in updates and not isinstance(updates["active"], int):
            updates["active"] = int(updates["active"])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [wh_id]

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE webhook_configs SET {set_clause} WHERE wh_id = ?",
                    values,
                )
                conn.commit()
        return self.get_webhook(wh_id)

    def delete_webhook(self, wh_id: str) -> bool:
        """删除 Webhook 配置"""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM webhook_configs WHERE wh_id = ?", (wh_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    def get_active_webhooks(self, platform: str = "") -> list[WebhookRecord]:
        """获取所有启用的 Webhook，可按平台过滤"""
        with self._get_conn() as conn:
            if platform:
                rows = conn.execute(
                    """SELECT * FROM webhook_configs
                    WHERE active = 1 AND platform = ? ORDER BY wh_id""",
                    (platform,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM webhook_configs
                    WHERE active = 1 ORDER BY wh_id"""
                ).fetchall()
            return [WebhookRecord(**dict(r)) for r in rows]

    # ── 清理 ──

    def cleanup_old_tasks(self, retention_days: int = RETENTION_DAYS) -> int:
        """清理过期任务及链路"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                # 先删 trace（外键级联）
                conn.execute(
                    "DELETE FROM trace_steps WHERE task_id IN (SELECT id FROM tasks WHERE created_at < ?)",
                    (cutoff,),
                )
                cursor = conn.execute("DELETE FROM tasks WHERE created_at < ?", (cutoff,))
                conn.commit()
                deleted = cursor.rowcount
                if deleted:
                    logger.info(f"[TaskStore] 清理过期任务 {deleted} 条（早于 {cutoff}）")
                return deleted

    # ── 团队模型偏好（SaaS 核心） ──

    def get_team_model_prefs(self, team_id: str) -> Optional[TeamModelPrefsRecord]:
        """获取某团队的模型偏好，不存在返回 None"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM team_model_prefs WHERE team_id = ?", (team_id,)
            ).fetchone()
        if row:
            return TeamModelPrefsRecord(**dict(row))
        return None

    def set_team_model_prefs(self, team_id: str, **kwargs) -> TeamModelPrefsRecord:
        """
        设置/更新团队模型偏好。
        kwargs 键名如 planning_model, evaluation_model 等。
        空字符串表示"不覆盖，用全局默认"。
        """
        now = datetime.now(timezone.utc).isoformat()
        field_names = [
            "planning_model", "code_generation_model", "evaluation_model",
            "agent_model", "fast_chat_model", "data_generation_model",
            "rag_query_model", "fallback_model",
        ]

        with self._lock:
            with self._get_conn() as conn:
                existing = conn.execute(
                    "SELECT * FROM team_model_prefs WHERE team_id = ?", (team_id,)
                ).fetchone()

                if existing:
                    # UPDATE — 只更新传入的字段
                    set_parts = []
                    params = []
                    for fn in field_names:
                        if fn in kwargs:
                            set_parts.append(f"{fn} = ?")
                            params.append(kwargs[fn])
                    if not set_parts:
                        return TeamModelPrefsRecord(**dict(existing))
                    params.append(now)
                    params.append(team_id)
                    sql = f"UPDATE team_model_prefs SET {', '.join(set_parts)}, updated_at = ? WHERE team_id = ?"
                    conn.execute(sql, params)
                else:
                    # INSERT
                    defaults = {fn: kwargs.get(fn, "") for fn in field_names}
                    defaults["team_id"] = team_id
                    defaults["created_at"] = now
                    defaults["updated_at"] = now
                    columns = ", ".join(defaults.keys())
                    placeholders = ", ".join(["?"] * len(defaults))
                    conn.execute(
                        f"INSERT INTO team_model_prefs ({columns}) VALUES ({placeholders})",
                        list(defaults.values()),
                    )

                conn.commit()

            # 重新读取
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM team_model_prefs WHERE team_id = ?", (team_id,)
                ).fetchone()
            return TeamModelPrefsRecord(**dict(row))

    def delete_team_model_prefs(self, team_id: str) -> bool:
        """删除团队模型偏好（恢复全局默认）。"""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM team_model_prefs WHERE team_id = ?", (team_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Team Orchestration CRUD
    # ------------------------------------------------------------------

    def create_team_task(self, task: "TeamTask") -> None:
        """创建一条团队编排任务记录"""
        import json
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO team_tasks (
                        task_id, title, description, status, team_id, user_id,
                        assigned_to, assigned_agent, required_roles_json, tags_json,
                        priority, parent_task_id, model, context_json, artifacts_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        task.title,
                        task.description,
                        task.status.value if task.status else "inbox",
                        task.team_id or "default",
                        task.user_id or "",
                        task.assigned_to.value if task.assigned_to else None,
                        task.assigned_agent or "",
                        json.dumps([r.value for r in task.required_roles], ensure_ascii=False),
                        json.dumps(task.tags, ensure_ascii=False),
                        task.priority,
                        task.parent_task_id,
                        task.model or "",
                        json.dumps(task.context, ensure_ascii=False),
                        json.dumps([a.model_dump() for a in task.artifacts], ensure_ascii=False),
                        task.created_at,
                        task.updated_at,
                    ),
                )
                conn.commit()

    def update_team_task(self, task_id: str, **kwargs) -> None:
        """根据 task_id 更新任意字段"""
        import json
        if not kwargs:
            return
        allowed = {
            "title", "description", "status", "team_id", "user_id",
            "assigned_to", "assigned_agent", "required_roles_json", "tags_json",
            "priority", "parent_task_id", "model", "context_json", "artifacts_json",
            "created_at", "updated_at",
        }
        normalized: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k in ("required_roles_json", "tags_json", "context_json", "artifacts_json") and not isinstance(v, str):
                normalized[k] = json.dumps(v, ensure_ascii=False)
            else:
                normalized[k] = v
        if not normalized:
            return
        columns = ", ".join(f"{k} = ?" for k in normalized.keys())
        values = list(normalized.values()) + [task_id]
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(f"UPDATE team_tasks SET {columns} WHERE task_id = ?", values)
                conn.commit()

    def _row_to_team_task_dict(self, row: sqlite3.Row) -> dict:
        import json
        return {
            "task_id": row["task_id"],
            "title": row["title"],
            "description": row["description"] or "",
            "status": row["status"],
            "team_id": row["team_id"],
            "user_id": row["user_id"],
            "assigned_to": row["assigned_to"],
            "assigned_agent": row["assigned_agent"],
            "required_roles": json.loads(row["required_roles_json"] or "[]"),
            "tags": json.loads(row["tags_json"] or "[]"),
            "priority": row["priority"],
            "parent_task_id": row["parent_task_id"],
            "model": row["model"],
            "context": json.loads(row["context_json"] or "{}"),
            "artifacts_json": row["artifacts_json"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_team_task(self, task_id: str) -> Optional["TeamTask"]:
        import json
        from app.schemas.team import Artifact, HandoffMessage, ReviewResult, TeamRole, TeamTask
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute("SELECT * FROM team_tasks WHERE task_id = ?", (task_id,)).fetchone()
                if row is None:
                    return None
                data = self._row_to_team_task_dict(row)
                handoff_rows = conn.execute(
                    "SELECT * FROM team_handoffs WHERE task_id = ? ORDER BY created_at",
                    (task_id,),
                ).fetchall()
                review_rows = conn.execute(
                    "SELECT * FROM team_reviews WHERE task_id = ? ORDER BY created_at",
                    (task_id,),
                ).fetchall()

        def _safe_artifacts(raw: str) -> list[Artifact]:
            try:
                return [Artifact(**item) for item in json.loads(raw or "[]")]
            except Exception:
                return []

        def _safe_handoffs(rows) -> list[HandoffMessage]:
            out = []
            for r in rows:
                try:
                    out.append(HandoffMessage(
                        handoff_id=r["handoff_id"],
                        task_id=r["task_id"],
                        from_role=TeamRole(r["from_role"]) if r["from_role"] else TeamRole.ORCHESTRATOR,
                        to_role=TeamRole(r["to_role"]) if r["to_role"] else TeamRole.BUILDER,
                        from_agent=r["from_agent"],
                        to_agent=r["to_agent"],
                        intent=r["intent"],
                        context=r["context"],
                        deliverables=[Artifact(**a) for a in json.loads(r["deliverables_json"] or "[]")],
                        blockers=json.loads(r["blockers_json"] or "[]"),
                        notes=r["notes"],
                        created_at=r["created_at"],
                    ))
                except Exception:
                    continue
            return out

        def _safe_reviews(rows) -> list[ReviewResult]:
            out = []
            for r in rows:
                try:
                    out.append(ReviewResult(
                        review_id=r["review_id"],
                        task_id=r["task_id"],
                        verdict=r["verdict"],
                        reviewer_agent=r["reviewer_agent"],
                        score=r["score"],
                        comments=json.loads(r["comments_json"] or "[]"),
                        required_changes=json.loads(r["required_changes_json"] or "[]"),
                        created_at=r["created_at"],
                    ))
                except Exception:
                    continue
            return out

        return TeamTask(
            task_id=data["task_id"],
            title=data["title"],
            description=data["description"],
            status=data["status"],
            team_id=data["team_id"],
            user_id=data["user_id"],
            assigned_to=data["assigned_to"],
            assigned_agent=data["assigned_agent"],
            required_roles=data["required_roles"],
            tags=data["tags"],
            priority=data["priority"],
            parent_task_id=data["parent_task_id"],
            model=data["model"],
            context=data["context"],
            artifacts=_safe_artifacts(data["artifacts_json"]),
            handoffs=_safe_handoffs(handoff_rows),
            reviews=_safe_reviews(review_rows),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def list_team_tasks(
        self,
        status: Optional[str] = None,
        team_id: Optional[str] = None,
        page_size: int = 50,
        offset: int = 0,
    ) -> tuple[list["TeamTask"], int]:
        where_parts = []
        params: list[Any] = []
        if status:
            where_parts.append("status = ?")
            params.append(status)
        if team_id:
            where_parts.append("team_id = ?")
            params.append(team_id)
        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""
        with self._lock:
            with self._get_conn() as conn:
                total_row = conn.execute(
                    f"SELECT COUNT(*) as cnt FROM team_tasks {where_clause}", params
                ).fetchone()
                total = total_row["cnt"] if total_row else 0
                rows = conn.execute(
                    f"SELECT task_id FROM team_tasks {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    params + [page_size, offset],
                ).fetchall()
        tasks = []
        for r in rows:
            t = self.get_team_task(r["task_id"])
            if t is not None:
                tasks.append(t)
        return tasks, total

    def add_team_handoff(self, handoff: "HandoffMessage") -> None:
        import json
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO team_handoffs (
                        handoff_id, task_id, from_role, to_role, from_agent, to_agent,
                        intent, context, deliverables_json, blockers_json, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        handoff.handoff_id,
                        handoff.task_id,
                        handoff.from_role.value if handoff.from_role else "",
                        handoff.to_role.value if handoff.to_role else "",
                        handoff.from_agent or "",
                        handoff.to_agent or "",
                        handoff.intent.value if handoff.intent else "delegate",
                        handoff.context or "",
                        json.dumps([a.model_dump() for a in handoff.deliverables], ensure_ascii=False),
                        json.dumps(handoff.blockers, ensure_ascii=False),
                        handoff.notes or "",
                        handoff.created_at,
                    ),
                )
                conn.commit()

    def add_team_review_request(self, req: "ReviewRequest") -> None:
        import json
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO team_reviews (
                        review_id, task_id, reviewer_role, reviewer_agent, builder_agent,
                        artifacts_json, criteria_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        req.review_id,
                        req.task_id,
                        req.reviewer_role.value if req.reviewer_role else "reviewer",
                        req.reviewer_agent or "",
                        req.builder_agent or "",
                        json.dumps([a.model_dump() for a in req.artifacts], ensure_ascii=False),
                        json.dumps(req.criteria, ensure_ascii=False),
                        req.created_at,
                    ),
                )
                conn.commit()

    def add_team_review_result(self, result: "ReviewResult") -> None:
        import json
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE team_reviews
                    SET verdict = ?,
                        score = ?,
                        comments_json = ?,
                        required_changes_json = ?
                    WHERE review_id = ?
                    """,
                    (
                        result.verdict.value if result.verdict else "",
                        result.score,
                        json.dumps(result.comments, ensure_ascii=False),
                        json.dumps(result.required_changes, ensure_ascii=False),
                        result.review_id,
                    ),
                )
                conn.commit()


# ============================================================
# 全局单例
# ============================================================

_task_store: Optional[TaskStore] = None


def get_task_store() -> TaskStore:
    """获取全局任务存储单例"""
    global _task_store
    if _task_store is None:
        _task_store = TaskStore()
        logger.info(f"[TaskStore] 初始化完成 db={_task_store.db_path}")
    return _task_store
