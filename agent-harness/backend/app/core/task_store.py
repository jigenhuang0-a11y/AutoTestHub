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
import uuid
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class _StubRecord:
    """未实现存储方法返回的占位记录，支持 .to_dict() 以避免新增端点 500。"""

    def __init__(self, **data):
        self._data = data

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._data.get(name)

    def __iter__(self):
        return iter(self._data.items())

    def __getitem__(self, key):
        return self._data[key]

    def to_dict(self):
        return self._data.copy()


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


@dataclass
class EnvironmentRecord:
    """测试环境配置记录（环境管理页面）"""
    id: Optional[int] = None
    env_id: str = ""                         # 对外 ID 如 env-1
    name: str = ""                            # 预发环境 / 生产环境
    env_type: str = "test"                    # test / staging / prod
    base_url: str = ""
    description: str = ""
    owner: str = ""
    status: str = "active"                    # active / inactive
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.env_id,
            "name": self.name,
            "env_type": self.env_type,
            "base_url": self.base_url,
            "description": self.description,
            "owner": self.owner,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ============================================================
# 数据工厂 (DataFactory) 记录
# ============================================================

@dataclass
class DatasetRecord:
    """数据工厂 - 数据集记录"""
    id: Optional[int] = None
    ds_id: str = ""
    name: str = ""
    description: str = ""
    schema_def: list = field(default_factory=list)
    records: list = field(default_factory=list)
    row_count: int = 0
    status: str = "completed"   # pending / running / completed / failed
    error: str = ""
    tags: list = field(default_factory=list)
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "ds_id": self.ds_id,
            "name": self.name,
            "description": self.description,
            "schema_def": self.schema_def,
            "records": self.records,
            "row_count": self.row_count,
            "record_count": self.row_count,
            "status": self.status,
            "error": self.error,
            "tags": self.tags,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class TestSuiteRecord:
    """测试套件记录"""
    id: Optional[int] = None
    suite_id: str = ""
    name: str = ""
    description: str = ""
    project: str = ""
    module: str = ""
    case_count: int = 0
    last_execution_status: str = ""   # passed / failed / running / pending / ""
    last_execution_at: str = ""
    schedule_enabled: bool = False
    schedule_cron: str = ""
    tags: list = field(default_factory=list)
    creator: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "suite_id": self.suite_id,
            "name": self.name,
            "description": self.description,
            "project": self.project,
            "module": self.module,
            "case_count": self.case_count,
            "last_execution_status": self.last_execution_status,
            "last_execution_at": self.last_execution_at,
            "schedule_enabled": self.schedule_enabled,
            "schedule_cron": self.schedule_cron,
            "tags": self.tags,
            "creator": self.creator,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class TestcaseRecord:
    """接口测试用例记录"""
    id: Optional[int] = None
    case_id: str = ""
    project: str = ""
    module: str = ""
    title: str = ""
    description: str = ""
    method: str = "GET"
    api_endpoint: str = ""
    priority: str = "P2"
    status: str = "draft"            # draft / active / disabled
    tags: list = field(default_factory=list)
    creator: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "case_id": self.case_id,
            "project": self.project,
            "module": self.module,
            "title": self.title,
            "description": self.description,
            "method": self.method,
            "api_endpoint": self.api_endpoint,
            "priority": self.priority,
            "status": self.status,
            "tags": self.tags,
            "creator": self.creator,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class PerfPlanRecord:
    """性能测试计划记录"""
    id: Optional[int] = None
    plan_id: str = ""
    name: str = ""
    description: str = ""
    target_url: str = ""
    engine: str = "locust"           # locust / jmeter / k6
    concurrency: int = 0
    duration: int = 0
    ramp_up: int = 0
    status: str = "draft"            # draft / active / running / completed / failed
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "target_url": self.target_url,
            "engine": self.engine,
            "concurrency": self.concurrency,
            "duration": self.duration,
            "ramp_up": self.ramp_up,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class WebExecutionRecord:
    """Web/UI 自动化执行记录"""
    id: Optional[int] = None
    exec_id: str = ""
    test_case: str = ""
    test_case_title: str = ""
    status: str = "passed"        # passed / failed / error / running / pending
    executed_at: str = ""
    executed_by: str = ""
    executed_by_username: str = ""
    duration_ms: int = 0
    screenshot: str = ""
    error_message: str = ""
    steps_total: int = 0
    steps_passed: int = 0
    created_at: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "exec_id": self.exec_id,
            "test_case": self.test_case,
            "test_case_title": self.test_case_title,
            "status": self.status,
            "executed_at": self.executed_at,
            "executed_by": self.executed_by,
            "executed_by_username": self.executed_by_username,
            "duration_ms": self.duration_ms,
            "screenshot": self.screenshot,
            "error_message": self.error_message,
            "steps_total": self.steps_total,
            "steps_passed": self.steps_passed,
            "created_at": self.created_at,
        }


@dataclass
class WebTestCaseRecord:
    """Web/UI 自动化测试用例"""
    id: Optional[int] = None
    tc_id: str = ""
    title: str = ""
    description: str = ""
    priority: str = "P2"
    target_url: str = ""
    engine: str = "playwright"
    status: str = "active"
    ai_prompt: str = ""
    steps: Any = field(default_factory=list)
    assertions: Any = field(default_factory=list)
    browser_type: str = "chromium"
    browser_config: Any = field(default_factory=dict)
    cookies: Any = field(default_factory=list)
    screenshot_enabled: bool = True
    record_video: bool = False
    full_page_screenshot: bool = False
    tags: Any = field(default_factory=list)
    created_by: str = ""
    created_by_username: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self):
        return {
            "id": self.tc_id,
            "tc_id": self.tc_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "target_url": self.target_url,
            "page_url": self.target_url,
            "engine": self.engine,
            "status": self.status,
            "ai_prompt": self.ai_prompt,
            "steps": self.steps if isinstance(self.steps, list) else json.loads(self.steps or "[]"),
            "assertions": self.assertions if isinstance(self.assertions, list) else json.loads(self.assertions or "[]"),
            "assertion_rules": self.assertions if isinstance(self.assertions, list) else json.loads(self.assertions or "[]"),
            "browser_type": self.browser_type,
            "browser_config": self.browser_config if isinstance(self.browser_config, dict) else json.loads(self.browser_config or "{}"),
            "cookies": self.cookies if isinstance(self.cookies, list) else json.loads(self.cookies or "[]"),
            "screenshot_enabled": self.screenshot_enabled,
            "record_video": self.record_video,
            "full_page_screenshot": self.full_page_screenshot,
            "tags": self.tags if isinstance(self.tags, list) else json.loads(self.tags or "[]"),
            "created_by": self.created_by,
            "created_by_username": self.created_by_username,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class PerfExecutionRecord:
    """性能测试执行记录"""
    id: Optional[int] = None
    exec_id: str = ""
    test_case: str = ""
    test_case_name: str = ""
    status: str = "completed"     # completed / running / failed / stopped / pending
    started_at: str = ""
    started_by: str = ""
    started_by_name: str = ""
    duration: int = 0
    total_requests: int = 0
    failures: int = 0
    requests_per_second: float = 0.0
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    error_rate: float = 0.0
    engine: str = "locust"
    exec_summary: str = ""
    created_at: str = ""

    def to_dict(self):
        summary = {}
        if self.exec_summary:
            try:
                summary = json.loads(self.exec_summary)
            except (json.JSONDecodeError, TypeError):
                summary = {}
        return {
            "id": self.id,
            "exec_id": self.exec_id,
            "test_case": self.test_case,
            "test_case_name": self.test_case_name,
            "status": self.status,
            "started_at": self.started_at,
            "started_by": self.started_by,
            "started_by_name": self.started_by_name,
            "duration": self.duration,
            "total_requests": self.total_requests,
            "failures": self.failures,
            "requests_per_second": self.requests_per_second,
            "avg_response_time": self.avg_response_time,
            "p95_response_time": self.p95_response_time,
            "error_rate": self.error_rate,
            "engine": self.engine,
            "exec_summary": summary,
            "created_at": self.created_at,
        }


@dataclass
class TemplateRecord:
    """数据工厂 - 模板记录"""
    id: Optional[int] = None
    tpl_id: str = ""
    name: str = ""
    description: str = ""
    domain: str = ""
    category: str = ""
    scenario: str = ""
    config: dict = field(default_factory=dict)
    variables: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "tpl_id": self.tpl_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "category": self.category,
            "scenario": self.scenario,
            "config": self.config,
            "variables": self.variables,
            "tags": self.tags,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
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
        """建表 + 索引；对之前未实现真实存储的表做简单迁移"""
        with self._get_conn() as conn:
            # web_testcases 表在旧版本不存在或为占位空表结构；此处直接重建以应用最新 schema
            conn.execute("DROP TABLE IF EXISTS web_testcases")
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

                -- 测试执行记录表（报告页数据源）
                CREATE TABLE IF NOT EXISTS executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exec_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'completed',
                    total_cases INTEGER NOT NULL DEFAULT 0,
                    passed_cases INTEGER NOT NULL DEFAULT 0,
                    failed_cases INTEGER NOT NULL DEFAULT 0,
                    skipped_cases INTEGER NOT NULL DEFAULT 0,
                    duration REAL NOT NULL DEFAULT 0,
                    trigger_type TEXT NOT NULL DEFAULT 'manual',
                    summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_executions_exec_id ON executions(exec_id);
                CREATE INDEX IF NOT EXISTS idx_executions_created ON executions(created_at DESC);

                -- 测试执行明细表
                CREATE TABLE IF NOT EXISTS execution_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exec_id TEXT NOT NULL,
                    case_id TEXT NOT NULL DEFAULT '',
                    case_title TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    response_body TEXT NOT NULL DEFAULT '',
                    assertions TEXT NOT NULL DEFAULT '[]',
                    extracted_vars TEXT NOT NULL DEFAULT '{}',
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_execution_results_exec_id ON execution_results(exec_id);

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

            # ── 测试环境配置表（环境管理页面） ──
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS environments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    env_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    env_type TEXT NOT NULL DEFAULT 'test',   -- test/staging/prod
                    base_url TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_environments_env_id ON environments(env_id);
            """)

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

                -- 数据工厂：数据集表
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
                CREATE INDEX IF NOT EXISTS idx_datafactory_datasets_created ON datafactory_datasets(created_at DESC);

                -- 数据工厂：模板表
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
                CREATE INDEX IF NOT EXISTS idx_datafactory_templates_created ON datafactory_templates(created_at DESC);

                -- 测试套件表
                CREATE TABLE IF NOT EXISTS testsuites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    suite_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    project TEXT NOT NULL DEFAULT '',
                    module TEXT NOT NULL DEFAULT '',
                    case_count INTEGER NOT NULL DEFAULT 0,
                    last_execution_status TEXT NOT NULL DEFAULT '',
                    last_execution_at TEXT NOT NULL DEFAULT '',
                    schedule_enabled INTEGER NOT NULL DEFAULT 0,
                    schedule_cron TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '[]',
                    creator TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                -- 接口测试用例表
                CREATE TABLE IF NOT EXISTS testcases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL UNIQUE,
                    project TEXT NOT NULL DEFAULT '',
                    module TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    method TEXT NOT NULL DEFAULT 'GET',
                    api_endpoint TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'P2',
                    status TEXT NOT NULL DEFAULT 'draft',
                    tags TEXT NOT NULL DEFAULT '[]',
                    creator TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                -- 性能测试计划表
                CREATE TABLE IF NOT EXISTS perf_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    target_url TEXT NOT NULL DEFAULT '',
                    engine TEXT NOT NULL DEFAULT 'locust',
                    concurrency INTEGER NOT NULL DEFAULT 0,
                    duration INTEGER NOT NULL DEFAULT 0,
                    ramp_up INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                -- Web/UI 自动化测试用例表
                CREATE TABLE IF NOT EXISTS web_testcases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tc_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'P2',
                    target_url TEXT NOT NULL DEFAULT '',
                    engine TEXT NOT NULL DEFAULT 'playwright',
                    status TEXT NOT NULL DEFAULT 'active',
                    ai_prompt TEXT NOT NULL DEFAULT '',
                    steps TEXT NOT NULL DEFAULT '[]',
                    assertions TEXT NOT NULL DEFAULT '[]',
                    browser_type TEXT NOT NULL DEFAULT 'chromium',
                    browser_config TEXT NOT NULL DEFAULT '{}',
                    cookies TEXT NOT NULL DEFAULT '[]',
                    screenshot_enabled INTEGER NOT NULL DEFAULT 1,
                    record_video INTEGER NOT NULL DEFAULT 0,
                    full_page_screenshot INTEGER NOT NULL DEFAULT 0,
                    tags TEXT NOT NULL DEFAULT '[]',
                    created_by TEXT NOT NULL DEFAULT '',
                    created_by_username TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                -- Web/UI 自动化执行记录表
                CREATE TABLE IF NOT EXISTS web_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exec_id TEXT NOT NULL UNIQUE,
                    test_case TEXT NOT NULL DEFAULT '',
                    test_case_title TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'passed',
                    executed_at TEXT NOT NULL DEFAULT '',
                    executed_by TEXT NOT NULL DEFAULT '',
                    executed_by_username TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    screenshot TEXT NOT NULL DEFAULT '',
                    error_message TEXT NOT NULL DEFAULT '',
                    steps_total INTEGER NOT NULL DEFAULT 0,
                    steps_passed INTEGER NOT NULL DEFAULT 0,
                    result_data TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                -- 性能测试执行记录表
                CREATE TABLE IF NOT EXISTS perf_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exec_id TEXT NOT NULL UNIQUE,
                    test_case TEXT NOT NULL DEFAULT '',
                    test_case_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'completed',
                    started_at TEXT NOT NULL DEFAULT '',
                    started_by TEXT NOT NULL DEFAULT '',
                    started_by_name TEXT NOT NULL DEFAULT '',
                    duration INTEGER NOT NULL DEFAULT 0,
                    total_requests INTEGER NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0,
                    requests_per_second REAL NOT NULL DEFAULT 0,
                    avg_response_time REAL NOT NULL DEFAULT 0,
                    p95_response_time REAL NOT NULL DEFAULT 0,
                    error_rate REAL NOT NULL DEFAULT 0,
                    engine TEXT NOT NULL DEFAULT 'locust',
                    exec_summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                -- 知识库表
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    kb_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    embedding_model TEXT NOT NULL DEFAULT 'bge-m3',
                    doc_count INTEGER NOT NULL DEFAULT 0,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- 知识库文档表
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    kb_id TEXT NOT NULL,
                    filename TEXT NOT NULL DEFAULT '',
                    file_size INTEGER NOT NULL DEFAULT 0,
                    file_type TEXT NOT NULL DEFAULT '',
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(kb_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_documents_kb_id ON documents(kb_id);

                -- 日常对话/知识库问答会话表
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    mode TEXT NOT NULL DEFAULT 'chat',
                    kb_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- 会话消息表
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    eval_score REAL,
                    needs_human INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);
            """)
            conn.commit()

            # 迁移：为已存在的旧表补充 status / error 列（旧 schema 可能缺少）
            self._migrate_datafactory_columns(conn)
            # 迁移：测试管理三表补充新列（演示库可能用旧 schema）
            self._migrate_test_mgmt_columns(conn)
            # 迁移：知识库表补充统计列、创建文档表（旧 schema 可能没有）
            self._migrate_knowledge_base_columns(conn)

    def _migrate_test_mgmt_columns(self, conn):
        """兼容旧 schema：为 testsuites / testcases / perf_plans 补齐新列。"""
        try:
            # testsuites：旧表有 suite_id/created_by，缺 module/case_count/状态/调度列
            cols = {r[1] for r in conn.execute("PRAGMA table_info(testsuites)").fetchall()}
            for col, ddl in [
                ("module", "TEXT NOT NULL DEFAULT ''"),
                ("case_count", "INTEGER NOT NULL DEFAULT 0"),
                ("last_execution_status", "TEXT NOT NULL DEFAULT ''"),
                ("last_execution_at", "TEXT NOT NULL DEFAULT ''"),
                ("schedule_enabled", "INTEGER NOT NULL DEFAULT 0"),
                ("schedule_cron", "TEXT NOT NULL DEFAULT ''"),
                ("creator", "TEXT NOT NULL DEFAULT ''"),
            ]:
                if col not in cols:
                    conn.execute(f"ALTER TABLE testsuites ADD COLUMN {col} {ddl}")
            if "creator" not in cols and "created_by" in cols:
                conn.execute("UPDATE testsuites SET creator = created_by WHERE creator = ''")

            # testcases：旧表用 tc_id，新代码用 case_id
            cols = {r[1] for r in conn.execute("PRAGMA table_info(testcases)").fetchall()}
            if "case_id" not in cols and "tc_id" in cols:
                conn.execute("ALTER TABLE testcases ADD COLUMN case_id TEXT NOT NULL DEFAULT ''")
                conn.execute("UPDATE testcases SET case_id = tc_id WHERE case_id = ''")

            # perf_plans：旧表用 pp_id/scenario/creator，新代码用 plan_id/engine/created_by
            cols = {r[1] for r in conn.execute("PRAGMA table_info(perf_plans)").fetchall()}
            if "plan_id" not in cols and "pp_id" in cols:
                conn.execute("ALTER TABLE perf_plans ADD COLUMN plan_id TEXT NOT NULL DEFAULT ''")
                conn.execute("UPDATE perf_plans SET plan_id = pp_id WHERE plan_id = ''")
            for col, ddl in [("engine", "TEXT NOT NULL DEFAULT 'locust'"),
                             ("created_by", "TEXT NOT NULL DEFAULT ''")]:
                if col not in cols:
                    conn.execute(f"ALTER TABLE perf_plans ADD COLUMN {col} {ddl}")
            if "created_by" not in cols and "creator" in cols:
                conn.execute("UPDATE perf_plans SET created_by = creator WHERE created_by = ''")
            conn.commit()
        except Exception as e:
            logger.warning(f"[TaskStore] 迁移测试管理表列失败: {e}")

    def _migrate_knowledge_base_columns(self, conn):
        """兼容旧 schema：为 knowledge_bases 补充 doc_count/chunk_count，创建 documents 表。"""
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(knowledge_bases)").fetchall()}
            for col, ddl in [
                ("doc_count", "INTEGER NOT NULL DEFAULT 0"),
                ("chunk_count", "INTEGER NOT NULL DEFAULT 0"),
            ]:
                if col not in cols:
                    conn.execute(f"ALTER TABLE knowledge_bases ADD COLUMN {col} {ddl}")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    kb_id TEXT NOT NULL,
                    filename TEXT NOT NULL DEFAULT '',
                    file_size INTEGER NOT NULL DEFAULT 0,
                    file_type TEXT NOT NULL DEFAULT '',
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(kb_id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_kb_id ON documents(kb_id)")
            conn.commit()
        except Exception as e:
            logger.warning(f"[TaskStore] 迁移知识库表列失败: {e}")

    def _migrate_datafactory_columns(self, conn):
        """若 datafactory_datasets 表缺少 status/error 列，则 ALTER 补齐。"""
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(datafactory_datasets)").fetchall()}
            if "status" not in cols:
                conn.execute("ALTER TABLE datafactory_datasets ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'")
            if "error" not in cols:
                conn.execute("ALTER TABLE datafactory_datasets ADD COLUMN error TEXT NOT NULL DEFAULT ''")
            conn.commit()
        except Exception as e:
            logger.warning(f"[TaskStore] 迁移 datafactory_datasets 列失败: {e}")

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

            # 种子测试套件 / 接口用例 / 性能计划
            self._seed_test_mgmt(conn, now)

    def _seed_test_mgmt(self, conn, now: str):
        """为测试管理三页写入演示数据（首次启动、表为空时）"""
        # 测试套件
        if conn.execute("SELECT COUNT(*) FROM testsuites").fetchone()[0] == 0:
            suite_rows = [
                ("suite-1001", "用户中心回归套件", "覆盖登录/注册/个人中心的回归用例集", "用户中心", "account",
                 28, "passed", "2026-08-12 09:30", 1, "0 9 * * 1", '["回归","P1"]', "张三", now, now),
                ("suite-1002", "支付链路冒烟套件", "支付下单到回调的核心冒烟", "支付", "pay",
                 15, "failed", "2026-08-12 14:05", 0, "", '["冒烟","P0"]', "李四", now, now),
                ("suite-1003", "商品搜索性能套件", "搜索接口稳定性与性能", "商品", "search",
                 12, "running", "2026-08-13 08:50", 1, "0 */2 * * *", '["性能"]', "王五", now, now),
                ("suite-1004", "订单履约 E2E", "下单→履约→发货全链路", "订单", "order",
                 34, "passed", "2026-08-11 19:20", 0, "", '["E2E","P1"]', "张三", now, now),
                ("suite-1005", "风控规则回归", "风控拦截与放行规则", "风控", "risk",
                 9, "", "", 0, "", '["回归"]', "赵六", now, now),
                ("suite-1006", "消息推送套件", "站内信/短信/推送通道", "消息", "notify",
                 7, "passed", "2026-08-10 16:40", 1, "30 1 * * *", '["P2"]', "李四", now, now),
            ]
            conn.executemany(
                """INSERT INTO testsuites
                (suite_id, name, description, project, module, case_count, last_execution_status,
                 last_execution_at, schedule_enabled, schedule_cron, tags, creator, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                suite_rows,
            )
            conn.commit()
            logger.info(f"[TaskStore] 已写入 {len(suite_rows)} 条种子测试套件")

        # 接口测试用例
        if conn.execute("SELECT COUNT(*) FROM testcases").fetchone()[0] == 0:
            methods = ["GET", "POST", "PUT", "DELETE", "POST", "GET"]
            projects = ["用户中心", "支付", "商品", "订单", "风控", "消息"]
            modules = ["account", "pay", "search", "order", "risk", "notify"]
            titles = [
                "获取用户基本信息", "创建支付订单", "更新商品库存", "删除过期订单",
                "提交风控审核", "查询推送记录",
            ]
            eps = [
                "/api/v1/user/info", "/api/v1/pay/order", "/api/v1/product/stock",
                "/api/v1/order/expire", "/api/v1/risk/review", "/api/v1/notify/log",
            ]
            statuses = ["active", "active", "draft", "active", "disabled", "active"]
            priorities = ["P1", "P0", "P2", "P1", "P1", "P2"]
            case_rows = [
                (f"case-200{i + 1}", projects[i], modules[i], titles[i], "演示接口用例",
                 methods[i], eps[i], priorities[i], statuses[i], '["demo"]', "张三", now, now)
                for i in range(6)
            ]
            # 兼容旧表（可能用 tc_id 而非 case_id）
            tc_cols = {r[1] for r in conn.execute("PRAGMA table_info(testcases)").fetchall()}
            if "tc_id" in tc_cols:
                # 旧表同时存在 tc_id（NOT NULL）与新增 case_id，两者都填
                conn.executemany(
                    """INSERT INTO testcases
                    (tc_id, case_id, project, module, title, description, method, api_endpoint, priority, status, tags, creator, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [(r[0], r[0], *r[1:]) for r in case_rows],
                )
            else:
                conn.executemany(
                    """INSERT INTO testcases
                    (case_id, project, module, title, description, method, api_endpoint, priority, status, tags, creator, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    case_rows,
                )
            conn.commit()
            logger.info(f"[TaskStore] 已写入 {len(case_rows)} 条种子接口用例")

        # 性能测试计划
        if conn.execute("SELECT COUNT(*) FROM perf_plans").fetchone()[0] == 0:
            plan_rows = [
                ("plan-3001", "登录接口基准压测", "模拟峰值登录 QPS", "https://api.example.com/api/v1/user/login",
                 "locust", 200, 300, 30, "completed", "张三", now, now),
                ("plan-3002", "下单链路容量测试", "阶梯加压到上限", "https://api.example.com/api/v1/order/create",
                 "jmeter", 500, 600, 60, "running", "李四", now, now),
                ("plan-3003", "搜索接口稳定性", "长时间稳定性压测", "https://api.example.com/api/v1/search",
                 "k6", 100, 1800, 10, "draft", "王五", now, now),
            ]
            # 兼容旧表（可能用 pp_id 而非 plan_id）
            pp_cols = {r[1] for r in conn.execute("PRAGMA table_info(perf_plans)").fetchall()}
            if "pp_id" in pp_cols:
                # 旧表同时存在 pp_id（NOT NULL）与新增 plan_id，两者都填
                conn.executemany(
                    """INSERT INTO perf_plans
                    (pp_id, plan_id, name, description, target_url, engine, concurrency, duration, ramp_up, status, created_by, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [(r[0], r[0], *r[1:]) for r in plan_rows],
                )
            else:
                conn.executemany(
                    """INSERT INTO perf_plans
                    (plan_id, name, description, target_url, engine, concurrency, duration, ramp_up, status, created_by, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    plan_rows,
                )
            conn.commit()
            logger.info(f"[TaskStore] 已写入 {len(plan_rows)} 条种子性能计划")

        # 种子 Web/UI 自动化测试用例
        if conn.execute("SELECT COUNT(*) FROM web_testcases").fetchone()[0] == 0:
            base = datetime.now(timezone.utc)
            web_tc_rows = [
                (
                    "tc-web-0001", "登录页_正确账号登录", "验证使用有效账号密码可正常登录系统",
                    "P0", "https://example.com/login", "playwright", "active", "",
                    json.dumps([
                        {"action": "open", "selector": "", "value": "https://example.com/login"},
                        {"action": "fill", "selector": "#username", "value": "admin"},
                        {"action": "fill", "selector": "#password", "value": "password123"},
                        {"action": "click", "selector": "button[type=submit]"},
                        {"action": "waitForSelector", "selector": ".dashboard-header"},
                    ], ensure_ascii=False),
                    json.dumps([
                        {"type": "urlContains", "target": "/dashboard", "expected": "true"},
                        {"type": "elementExists", "target": ".user-name", "expected": "true"},
                    ], ensure_ascii=False),
                    "chromium", json.dumps({"headless": True}, ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    1, 0, 0,
                    json.dumps(["登录", "冒烟", "P0"], ensure_ascii=False),
                    "ai-base", "admin", base.isoformat(), base.isoformat(),
                ),
                (
                    "tc-web-0002", "购物车_添加商品", "选择商品 SKU 后加入购物车，验证购物车数量更新",
                    "P1", "https://example.com/products", "playwright", "active", "",
                    json.dumps([
                        {"action": "open", "selector": "", "value": "https://example.com/products"},
                        {"action": "click", "selector": ".product-card:first-child"},
                        {"action": "click", "selector": "button[data-action='add-to-cart']"},
                        {"action": "waitForSelector", "selector": ".toast-success"},
                        {"action": "click", "selector": "a[href='/cart']"},
                        {"action": "waitForSelector", "selector": ".cart-item"},
                    ], ensure_ascii=False),
                    json.dumps([
                        {"type": "elementTextContains", "target": ".cart-count", "expected": "1"},
                        {"type": "elementExists", "target": ".cart-item-title", "expected": "true"},
                    ], ensure_ascii=False),
                    "chromium", json.dumps({"headless": True}, ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    1, 0, 0,
                    json.dumps(["购物车", "核心流程"], ensure_ascii=False),
                    "ai-base", "admin", base.isoformat(), base.isoformat(),
                ),
                (
                    "tc-web-0003", "订单结算_优惠券抵扣", "结算页选择优惠券后，验证应付金额正确扣减",
                    "P1", "https://example.com/checkout", "playwright", "active", "",
                    json.dumps([
                        {"action": "open", "selector": "", "value": "https://example.com/checkout?order_id=ORD12345"},
                        {"action": "click", "selector": ".coupon-item:first-child"},
                        {"action": "waitForTimeout", "selector": "", "value": "500"},
                        {"action": "click", "selector": "button[data-action='place-order']"},
                        {"action": "waitForSelector", "selector": ".order-success"},
                    ], ensure_ascii=False),
                    json.dumps([
                        {"type": "elementTextContains", "target": ".final-amount", "expected": "89.00"},
                        {"type": "elementExists", "target": ".order-success", "expected": "true"},
                    ], ensure_ascii=False),
                    "chromium", json.dumps({"headless": True}, ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    1, 0, 0,
                    json.dumps(["订单", "优惠", "结算"], ensure_ascii=False),
                    "ai-base", "admin", base.isoformat(), base.isoformat(),
                ),
                (
                    "tc-web-0004", "个人中心_修改头像", "上传合法图片后，验证头像预览更新成功",
                    "P2", "https://example.com/profile", "playwright", "draft", "",
                    json.dumps([
                        {"action": "open", "selector": "", "value": "https://example.com/profile"},
                        {"action": "click", "selector": "#avatar-upload"},
                        {"action": "uploadFile", "selector": "input[type=file]", "value": "/tmp/avatar.png"},
                        {"action": "click", "selector": "button[data-action='save-avatar']"},
                        {"action": "waitForSelector", "selector": ".avatar-preview[src]"},
                    ], ensure_ascii=False),
                    json.dumps([
                        {"type": "elementExists", "target": ".avatar-preview[src]", "expected": "true"},
                    ], ensure_ascii=False),
                    "chromium", json.dumps({"headless": True}, ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    1, 0, 0,
                    json.dumps(["个人中心", "上传"], ensure_ascii=False),
                    "ai-base", "admin", base.isoformat(), base.isoformat(),
                ),
                (
                    "tc-web-0005", "搜索_关键词联想", "在搜索框输入关键词，验证下拉联想结果非空",
                    "P2", "https://example.com/search", "selenium", "active", "",
                    json.dumps([
                        {"action": "open", "selector": "", "value": "https://example.com/search"},
                        {"action": "fill", "selector": "#search-input", "value": "手机"},
                        {"action": "waitForTimeout", "selector": "", "value": "800"},
                    ], ensure_ascii=False),
                    json.dumps([
                        {"type": "elementExists", "target": ".suggest-item", "expected": "true"},
                        {"type": "elementCountGreaterThan", "target": ".suggest-item", "expected": "0"},
                    ], ensure_ascii=False),
                    "chrome", json.dumps({"headless": True}, ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    1, 0, 0,
                    json.dumps(["搜索", "Selenium"], ensure_ascii=False),
                    "ai-base", "admin", base.isoformat(), base.isoformat(),
                ),
            ]
            conn.executemany(
                """INSERT INTO web_testcases
                (tc_id, title, description, priority, target_url, engine, status, ai_prompt,
                 steps, assertions, browser_type, browser_config, cookies,
                 screenshot_enabled, record_video, full_page_screenshot, tags,
                 created_by, created_by_username, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                web_tc_rows,
            )
            conn.commit()
            logger.info(f"[TaskStore] 已写入 {len(web_tc_rows)} 条种子 Web 用例")

        # 种子 Web/UI 自动化执行记录（独立于套件/用例/计划，表空即补）
        if conn.execute("SELECT COUNT(*) FROM web_executions").fetchone()[0] == 0:
            base = datetime.now(timezone.utc)
            web_rows = [
                ("web-exec-0001", "tc-web-0001", "登录页_正确账号登录",
                 "passed", (base - timedelta(hours=2)).isoformat(),
                 "admin", "张伟", 4200, "login_pass.png", "", 5, 5,
                 json.dumps({"steps_results": [
                     {"step": 1, "action": "open", "status": "completed"},
                     {"step": 2, "action": "fill username", "status": "completed"},
                     {"step": 3, "action": "fill password", "status": "completed"},
                     {"step": 4, "action": "click submit", "status": "completed"},
                     {"step": 5, "action": "assert dashboard", "status": "completed"},
                 ]}, ensure_ascii=False)),
                ("web-exec-0002", "tc-web-0002", "购物车_添加商品",
                 "failed", (base - timedelta(hours=5)).isoformat(),
                 "admin", "张伟", 6800, "cart_fail.png", "元素定位超时: .add-to-cart-btn", 6, 4,
                 json.dumps({"steps_results": [
                     {"step": 1, "action": "open products", "status": "completed"},
                     {"step": 2, "action": "click product card", "status": "completed"},
                     {"step": 3, "action": "click add-to-cart", "status": "failed", "error": "Timeout 3000ms exceeded"},
                     {"step": 4, "action": "wait toast", "status": "skipped"},
                     {"step": 5, "action": "go cart", "status": "completed"},
                     {"step": 6, "action": "assert cart item", "status": "failed"},
                 ]}, ensure_ascii=False)),
                ("web-exec-0003", "tc-web-0003", "订单结算_优惠券抵扣",
                 "passed", (base - timedelta(days=1, hours=3)).isoformat(),
                 "tester01", "李娜", 5100, "checkout_pass.png", "", 7, 7,
                 json.dumps({"steps_results": [
                     {"step": 1, "action": "open checkout", "status": "completed"},
                     {"step": 2, "action": "select coupon", "status": "completed"},
                     {"step": 3, "action": "wait update", "status": "completed"},
                     {"step": 4, "action": "place order", "status": "completed"},
                     {"step": 5, "action": "assert success", "status": "completed"},
                 ]}, ensure_ascii=False)),
                ("web-exec-0004", "tc-web-0004", "个人中心_修改头像",
                 "error", (base - timedelta(days=1, hours=8)).isoformat(),
                 "tester01", "李娜", 2300, "", "上传接口 500 错误", 4, 2,
                 json.dumps({"steps_results": [
                     {"step": 1, "action": "open profile", "status": "completed"},
                     {"step": 2, "action": "click upload", "status": "completed"},
                     {"step": 3, "action": "upload file", "status": "completed"},
                     {"step": 4, "action": "save avatar", "status": "failed", "error": "POST /api/upload 500"},
                 ]}, ensure_ascii=False)),
                ("web-exec-0005", "tc-web-0005", "搜索_关键词联想",
                 "passed", (base - timedelta(days=2, hours=1)).isoformat(),
                 "admin", "张伟", 3900, "search_pass.png", "", 5, 5,
                 json.dumps({"steps_results": [
                     {"step": 1, "action": "open search", "status": "completed"},
                     {"step": 2, "action": "input keyword", "status": "completed"},
                     {"step": 3, "action": "wait suggest", "status": "completed"},
                 ]}, ensure_ascii=False)),
            ]
            conn.executemany(
                """INSERT INTO web_executions
                (exec_id, test_case, test_case_title, status, executed_at,
                 executed_by, executed_by_username, duration_ms, screenshot,
                 error_message, steps_total, steps_passed, result_data, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(r + (base.isoformat(),)) for r in web_rows],
            )
            conn.commit()
            logger.info(f"[TaskStore] 已写入 {len(web_rows)} 条种子 Web 执行记录")

        # 种子性能测试执行记录
        if conn.execute("SELECT COUNT(*) FROM perf_executions").fetchone()[0] == 0:
            base = datetime.now(timezone.utc)
            perf_rows = [
                ("perf-exec-0001", "perf-1", "登录接口基准测试",
                 "completed", (base - timedelta(hours=1)).isoformat(),
                 "admin", "张伟", 300, 15000, 45, 498.3, 212.5, 380.0, 0.003, "locust",
                 '{"score": 92, "summary": "登录接口在 300 并发下平均响应 212ms，满足 SLA。"}'),
                ("perf-exec-0002", "perf-2", "商品列表查询压测",
                 "completed", (base - timedelta(hours=4)).isoformat(),
                 "tester01", "李娜", 600, 42000, 320, 690.1, 540.8, 1180.0, 0.0076, "locust",
                 '{"score": 81, "summary": "商品列表在 600 并发下 P95 达 1.18s，需优化索引。"}'),
                ("perf-exec-0003", "perf-3", "下单链路全链路压测",
                 "failed", (base - timedelta(days=1, hours=2)).isoformat(),
                 "admin", "张伟", 300, 8800, 1240, 112.4, 1850.0, 3200.0, 0.141, "locust",
                 '{"score": 35, "summary": "下单链路口碑熔断，错误率 14%，数据库成为瓶颈。"}'),
                ("perf-exec-0004", "perf-4", "首页静态资源加载",
                 "completed", (base - timedelta(days=2, hours=6)).isoformat(),
                 "tester01", "李娜", 120, 96000, 60, 800.0, 95.2, 210.0, 0.0006, "locust",
                 '{"score": 95, "summary": "首页 CDN 命中率高，120 并发下响应极快。"}'),
            ]
            conn.executemany(
                """INSERT INTO perf_executions
                (exec_id, test_case, test_case_name, status, started_at,
                 started_by, started_by_name, duration, total_requests, failures,
                 requests_per_second, avg_response_time, p95_response_time, error_rate,
                 engine, exec_summary, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(r + (base.isoformat(),)) for r in perf_rows],
            )
            conn.commit()
            logger.info(f"[TaskStore] 已写入 {len(perf_rows)} 条种子性能执行记录")

        # 种子测试报告（汇总上述 Web/UI、性能、接口、套件数据）
        if conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0] == 0:
            base = datetime.now(timezone.utc)
            exec_rows = [
                (
                    "exec-report-0001",
                    f"全平台测试报告 {base.strftime('%Y-%m-%d %H:%M')}",
                    "completed", 15, 12, 2, 1,
                    245.6, "manual",
                    "全平台汇总：Web 5 条、性能 4 条、接口 6 条、套件 6 条；通过率 80.00%，失败率 13.33%，跳过率 6.67%。",
                    (base - timedelta(hours=1)).isoformat(),
                    (base - timedelta(hours=1)).isoformat(),
                ),
                (
                    "exec-report-0002",
                    f"全平台测试报告 {(base - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')}",
                    "completed", 10, 8, 1, 1,
                    198.4, "scheduled",
                    "全平台汇总：Web 3 条、性能 3 条、接口 4 条、套件 4 条；通过率 80.00%，失败率 10.00%，跳过率 10.00%。",
                    (base - timedelta(days=1)).isoformat(),
                    (base - timedelta(days=1)).isoformat(),
                ),
            ]
            conn.executemany(
                """INSERT INTO executions
                (exec_id, name, status, total_cases, passed_cases, failed_cases, skipped_cases,
                 duration, trigger_type, summary, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                exec_rows,
            )
            conn.commit()
            logger.info(f"[TaskStore] 已写入 {len(exec_rows)} 条种子测试报告")

            # 报告明细
            result_rows = [
                ("exec-report-0001", "web-0001", "Web 自动化执行 #1", "passed", 4200, ""),
                ("exec-report-0001", "web-0002", "Web 自动化执行 #2", "failed", 6800, "元素定位超时: .add-to-cart-btn"),
                ("exec-report-0001", "web-0003", "Web 自动化执行 #3", "passed", 5100, ""),
                ("exec-report-0001", "web-0004", "Web 自动化执行 #4", "failed", 2300, "上传接口 500 错误"),
                ("exec-report-0001", "web-0005", "Web 自动化执行 #5", "passed", 3900, ""),
                ("exec-report-0001", "perf-0001", "性能测试执行 #1", "passed", 300000, ""),
                ("exec-report-0001", "perf-0002", "性能测试执行 #2", "passed", 600000, ""),
                ("exec-report-0001", "perf-0003", "性能测试执行 #3", "failed", 300000, "错误率 14.1%，数据库成为瓶颈"),
                ("exec-report-0001", "perf-0004", "性能测试执行 #4", "passed", 120000, ""),
                ("exec-report-0001", "api-0001", "接口用例汇总", "passed", 0, ""),
                ("exec-report-0001", "api-0002", "接口用例汇总", "passed", 0, ""),
                ("exec-report-0001", "suite-0001", "测试套件汇总", "passed", 0, ""),
                ("exec-report-0001", "suite-0002", "测试套件汇总", "failed", 0, ""),
                ("exec-report-0002", "web-0001", "Web 自动化执行 #1", "passed", 4200, ""),
                ("exec-report-0002", "web-0002", "Web 自动化执行 #2", "passed", 6800, ""),
                ("exec-report-0002", "perf-0001", "性能测试执行 #1", "passed", 300000, ""),
                ("exec-report-0002", "api-0001", "接口用例汇总", "passed", 0, ""),
                ("exec-report-0002", "suite-0001", "测试套件汇总", "passed", 0, ""),
            ]
            conn.executemany(
                """INSERT INTO execution_results
                (exec_id, case_id, case_title, status, duration_ms, error_message, created_at)
                VALUES (?,?,?,?,?,?,?)""",
                [(r + (base.isoformat(),)) for r in result_rows],
            )
            conn.commit()
            logger.info(f"[TaskStore] 已写入 {len(result_rows)} 条种子报告明细")

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

    def get_active_prompt(self, agent_name: str, prompt_subtype: str = "default") -> Optional[PromptRecord]:
        """获取某 Agent 当前激活（is_active=1）的 Prompt，用于运行时热加载"""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT * FROM prompts
                   WHERE agent_name = ? AND prompt_subtype = ? AND is_active = 1
                   ORDER BY version DESC LIMIT 1""",
                (agent_name, prompt_subtype),
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

    def get_model_config_by_provider(self, provider: str) -> Optional[ModelConfigRecord]:
        """按 provider 取一条模型配置（用于把 DB 的 base_url 注入运行时 Provider）"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM model_configs WHERE provider = ? AND is_enabled = 1 LIMIT 1",
                (provider,),
            ).fetchone()
            if row is None:
                return None
            return ModelConfigRecord(**dict(row))

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

    def get_tenant_by_team(self, team: str) -> Optional[TenantRecord]:
        """按 team 字段取租户（限流用）"""
        if not team or team == "default":
            return None
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM tenants WHERE team = ? LIMIT 1", (team,)
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

    # ── 环境管理（Phase 2.6） ──

    def list_environments(self, env_type: str = "") -> list[EnvironmentRecord]:
        with self._get_conn() as conn:
            if env_type:
                rows = conn.execute(
                    "SELECT * FROM environments WHERE env_type = ? ORDER BY created_at DESC",
                    (env_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM environments ORDER BY created_at DESC"
                ).fetchall()
            return [EnvironmentRecord(**dict(r)) for r in rows]

    def get_environment(self, env_id: str) -> Optional[EnvironmentRecord]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM environments WHERE env_id = ?", (env_id,)
            ).fetchone()
            if row is None:
                return None
            return EnvironmentRecord(**dict(row))

    def create_environment(self, name: str, env_type: str = "test", base_url: str = "",
                           description: str = "", owner: str = "", status: str = "active") -> EnvironmentRecord:
        import uuid
        from datetime import datetime
        now = datetime.now().isoformat(timespec="seconds")
        env_id = f"env-{uuid.uuid4().hex[:8]}"
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO environments
                       (env_id, name, env_type, base_url, description, owner, status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (env_id, name, env_type, base_url, description, owner, status, now, now),
                )
                conn.commit()
        return self.get_environment(env_id)

    def update_environment(self, env_id: str, **kwargs) -> Optional[EnvironmentRecord]:
        allowed = {"name", "env_type", "base_url", "description", "owner", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return self.get_environment(env_id)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        from datetime import datetime
        now = datetime.now().isoformat(timespec="seconds")
        updates["updated_at"] = now
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE environments SET {set_clause} WHERE env_id = ?",
                    (*updates.values(), env_id),
                )
                conn.commit()
        return self.get_environment(env_id)

    def delete_environment(self, env_id: str) -> bool:
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM environments WHERE env_id = ?", (env_id,)
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
# 数据工厂 (DataFactory) 存储方法
# ============================================================

    def create_dataset(self, data: dict = None) -> DatasetRecord:
        """创建数据集（数据工厂）"""
        if data is None:
            data = {}
        ds_id = "ds-" + str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        name = data.get("name", "")
        description = data.get("description", "")
        schema_def = data.get("schema_def", "")
        records = data.get("records", False)
        if records is False:
            records = []
        if isinstance(records, list):
            records = json.dumps(records, ensure_ascii=False)
        row_count = data.get("row_count", 0)
        tags = data.get("tags", "")
        if tags is False or tags is None:
            tags = []
        if isinstance(tags, list):
            tags = json.dumps(tags, ensure_ascii=False)
        status = data.get("status", "completed")
        error = data.get("error", "")
        created_by = data.get("created_by", "")

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO datafactory_datasets
                    (ds_id, name, description, schema_def, records, row_count, status, error, tags,
                     created_by, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        ds_id, name, description, schema_def, records, row_count, status, error, tags,
                        created_by, now, now,
                    ),
                )
                conn.commit()
        return self.get_dataset(ds_id)

    def get_dataset(self, ds_id: str) -> Optional[DatasetRecord]:
        """获取单条数据集"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM datafactory_datasets WHERE ds_id = ?", (ds_id,)
            ).fetchone()
        if row is None:
            return None
        return DatasetRecord(**dict(row))

    def update_dataset(self, ds_id: str, data: dict) -> Optional[DatasetRecord]:
        """更新数据集字段（records / row_count / schema_def / tags / name / description）"""
        now = datetime.now(timezone.utc).isoformat()
        sets = ["updated_at = ?"]
        params = [now]
        for key in ("records", "row_count", "schema_def", "tags", "name", "description", "status", "error"):
            if key in data:
                if key in ("records", "schema_def", "tags") and isinstance(data[key], list):
                    sets.append(f"{key} = ?")
                    params.append(json.dumps(data[key], ensure_ascii=False))
                else:
                    sets.append(f"{key} = ?")
                    params.append(data[key])
        params.append(ds_id)
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE datafactory_datasets SET {', '.join(sets)} WHERE ds_id = ?",
                    params,
                )
                conn.commit()
        return self.get_dataset(ds_id)

    def list_datasets(self, page: int = 1, page_size: int = 20, tag: str = None) -> dict:
        """分页列出数据集，可选按 tag 模糊过滤"""
        sql = "SELECT * FROM datafactory_datasets"
        params = []
        if tag:
            sql += " WHERE tags LIKE ?"
            params.append(f"%{tag}%")
        sql += " ORDER BY created_at DESC"

        count_sql = f"SELECT COUNT(*) FROM ({sql})"
        with self._get_conn() as conn:
            total = conn.execute(count_sql, params).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"{sql} LIMIT ? OFFSET ?", params + [page_size, offset]
            ).fetchall()
        items = [DatasetRecord(**dict(r)) for r in rows]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def delete_dataset(self, ds_id: str) -> bool:
        """删除数据集，返回是否成功"""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM datafactory_datasets WHERE ds_id = ?", (ds_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    def list_templates(self, page: int = 1, page_size: int = 20) -> dict:
        """分页列出模板"""
        offset = (page - 1) * page_size
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM datafactory_templates"
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM datafactory_templates ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (page_size, offset),
            ).fetchall()
        items = [TemplateRecord(**dict(r)) for r in rows]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def create_template(self, data: dict) -> TemplateRecord:
        """创建模板"""
        tpl_id = "tpl-" + str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        name = data.get("name", "")
        description = data.get("description", "")
        domain = data.get("domain", "")
        category = data.get("category", "")
        scenario = data.get("scenario", "")
        config = data.get("config", {})
        if isinstance(config, dict):
            config = json.dumps(config, ensure_ascii=False)
        variables = data.get("variables", [])
        if isinstance(variables, list):
            variables = json.dumps(variables, ensure_ascii=False)
        tags = data.get("tags", [])
        if isinstance(tags, list):
            tags = json.dumps(tags, ensure_ascii=False)
        created_by = data.get("created_by", "")

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO datafactory_templates
                    (tpl_id, name, description, domain, category, scenario, config,
                     variables, tags, created_by, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        tpl_id, name, description, domain, category, scenario, config,
                        variables, tags, created_by, now, now,
                    ),
                )
                conn.commit()
        return self._get_template(tpl_id)

    def _get_template(self, tpl_id: str) -> Optional[TemplateRecord]:
        """获取单条模板"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM datafactory_templates WHERE tpl_id = ?", (tpl_id,)
            ).fetchone()
        if row is None:
            return None
        return TemplateRecord(**dict(row))

    def delete_template(self, tpl_id: str) -> bool:
        """删除模板，返回是否成功"""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM datafactory_templates WHERE tpl_id = ?", (tpl_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    # ============================================================
    # 测试管理列表：真实 SQLite 分页查询
    # ============================================================
    def _paginate(self, rows: list, page: int, page_size: int):
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        return rows[start:end], total

    @staticmethod
    def _row_to_record(row, record_cls):
        """把 sqlite Row 按 dataclass 字段过滤后构造记录，忽略多余列。"""
        fields = {f for f in record_cls.__dataclass_fields__}
        return record_cls(**{k: v for k, v in dict(row).items() if k in fields})

    def list_testsuites(self, keyword=None, project=None, module=None, status=None,
                        page=1, page_size=20):
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM testsuites WHERE 1=1"
                params = []
                if project:
                    sql += " AND project = ?"; params.append(project)
                if module:
                    sql += " AND module = ?"; params.append(module)
                if status:
                    sql += " AND last_execution_status = ?"; params.append(status)
                if keyword:
                    sql += " AND (name LIKE ? OR description LIKE ?)"
                    params.extend([f"%{keyword}%", f"%{keyword}%"])
                sql += " ORDER BY created_at DESC"
                rows = [self._row_to_record(r, TestSuiteRecord) for r in conn.execute(sql, params).fetchall()]
                page_rows, total = self._paginate(rows, page, page_size)
                return page_rows, total

    def list_testcases(self, project=None, module=None, status=None, priority=None,
                       keyword=None, page=1, page_size=20):
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM testcases WHERE 1=1"
                params = []
                if project:
                    sql += " AND project = ?"; params.append(project)
                if module:
                    sql += " AND module = ?"; params.append(module)
                if status:
                    sql += " AND status = ?"; params.append(status)
                if priority:
                    sql += " AND priority = ?"; params.append(priority)
                if keyword:
                    sql += " AND (title LIKE ? OR api_endpoint LIKE ? OR description LIKE ?)"
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
                sql += " ORDER BY created_at DESC"
                rows = [self._row_to_record(r, TestcaseRecord) for r in conn.execute(sql, params).fetchall()]
                page_rows, total = self._paginate(rows, page, page_size)
                return page_rows, total

    def list_perf_plans(self, status=None, keyword=None, page=1, page_size=20):
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM perf_plans WHERE 1=1"
                params = []
                if status:
                    sql += " AND status = ?"; params.append(status)
                if keyword:
                    sql += " AND (name LIKE ? OR target_url LIKE ? OR description LIKE ?)"
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
                sql += " ORDER BY created_at DESC"
                rows = [self._row_to_record(r, PerfPlanRecord) for r in conn.execute(sql, params).fetchall()]
                page_rows, total = self._paginate(rows, page, page_size)
                return page_rows, total

    def create_web_testcase(self, data: dict, created_by: str = "", created_by_username: str = "") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        tc_id = data.get("id") or ("tc-web-" + str(uuid.uuid4())[:8])
        steps = data.get("steps", [])
        if isinstance(steps, list):
            steps = json.dumps(steps, ensure_ascii=False)
        assertions = data.get("assertions", [])
        if isinstance(assertions, list):
            assertions = json.dumps(assertions, ensure_ascii=False)
        browser_config = data.get("browser_config", {})
        if isinstance(browser_config, dict):
            browser_config = json.dumps(browser_config, ensure_ascii=False)
        cookies = data.get("cookies", [])
        if isinstance(cookies, list):
            cookies = json.dumps(cookies, ensure_ascii=False)
        tags = data.get("tags", [])
        if isinstance(tags, list):
            tags = json.dumps(tags, ensure_ascii=False)
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO web_testcases
                    (tc_id, title, description, priority, target_url, engine, status, ai_prompt,
                     steps, assertions, browser_type, browser_config, cookies,
                     screenshot_enabled, record_video, full_page_screenshot, tags,
                     created_by, created_by_username, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        tc_id,
                        data.get("title", ""),
                        data.get("description", ""),
                        data.get("priority", "P2"),
                        data.get("target_url", ""),
                        data.get("engine", "playwright"),
                        data.get("status", "active"),
                        data.get("ai_prompt", ""),
                        steps,
                        assertions,
                        data.get("browser_type", "chromium"),
                        browser_config,
                        cookies,
                        int(bool(data.get("screenshot_enabled", True))),
                        int(bool(data.get("record_video", False))),
                        int(bool(data.get("full_page_screenshot", False))),
                        tags,
                        created_by,
                        created_by_username,
                        now, now,
                    ),
                )
                conn.commit()
        return self.get_web_testcase(tc_id)

    def get_web_testcase(self, tc_id: str) -> Optional[dict]:
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM web_testcases WHERE tc_id = ?", (tc_id,)
                ).fetchone()
                if not row:
                    return None
                d = dict(row)
                for k in ("steps", "assertions", "browser_config", "cookies", "tags"):
                    v = d.get(k)
                    if isinstance(v, str):
                        try:
                            d[k] = json.loads(v)
                        except Exception:
                            d[k] = [] if k != "browser_config" else {}
                d["id"] = d["tc_id"]
                return d

    def update_web_testcase(self, tc_id: str, data: dict) -> Optional[dict]:
        existing = self.get_web_testcase(tc_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        sets = []
        params = []
        for key in (
            "title", "description", "priority", "target_url", "engine", "status",
            "ai_prompt", "browser_type", "screenshot_enabled", "record_video", "full_page_screenshot",
        ):
            if key in data:
                sets.append(f"{key} = ?")
                params.append(data[key])
        for key in ("steps", "assertions", "browser_config", "cookies", "tags"):
            if key in data:
                sets.append(f"{key} = ?")
                v = data[key]
                if isinstance(v, (list, dict)):
                    v = json.dumps(v, ensure_ascii=False)
                params.append(v)
        sets.append("updated_at = ?")
        params.append(now)
        params.append(tc_id)
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE web_testcases SET {', '.join(sets)} WHERE tc_id = ?",
                    params,
                )
                conn.commit()
        return self.get_web_testcase(tc_id)

    def delete_web_testcase(self, tc_id: str) -> bool:
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM web_testcases WHERE tc_id = ?", (tc_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    def list_web_testcases(self, status=None, engine=None, keyword=None, page=1, page_size=20):
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM web_testcases WHERE 1=1"
                params = []
                if status:
                    sql += " AND status = ?"; params.append(status)
                if engine:
                    sql += " AND engine = ?"; params.append(engine)
                if keyword:
                    sql += " AND (title LIKE ? OR target_url LIKE ? OR description LIKE ?)"
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
                sql += " ORDER BY created_at DESC"
                rows = conn.execute(sql, params).fetchall()
                items = []
                for r in rows:
                    d = dict(r)
                    for k in ("steps", "assertions", "browser_config", "cookies", "tags"):
                        v = d.get(k)
                        if isinstance(v, str):
                            try:
                                d[k] = json.loads(v)
                            except Exception:
                                d[k] = [] if k != "browser_config" else {}
                    d["id"] = d["tc_id"]
                    items.append(d)
                total = len(items)
                start = (page - 1) * page_size
                end = start + page_size
                return items[start:end], total

    def create_web_execution(self, data: dict) -> dict:
        exec_id = data.get("exec_id") or ("exec-web-" + str(uuid.uuid4())[:8])
        now = datetime.now(timezone.utc).isoformat()
        result_data = data.get("result_data", {})
        if isinstance(result_data, dict):
            result_data = json.dumps(result_data, ensure_ascii=False)
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO web_executions
                    (exec_id, test_case, test_case_title, status, executed_at, executed_by,
                     executed_by_username, duration_ms, screenshot, error_message,
                     steps_total, steps_passed, result_data, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        exec_id,
                        data.get("test_case", ""),
                        data.get("test_case_title", ""),
                        data.get("status", "passed"),
                        data.get("executed_at") or now,
                        data.get("executed_by", ""),
                        data.get("executed_by_username", ""),
                        data.get("duration_ms", 0),
                        data.get("screenshot", ""),
                        data.get("error_message", ""),
                        data.get("steps_total", 0),
                        data.get("steps_passed", 0),
                        result_data,
                        now,
                    ),
                )
                conn.commit()
        return {"exec_id": exec_id, "id": exec_id}

    def get_web_execution(self, exec_id: str) -> Optional[dict]:
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM web_executions WHERE exec_id = ?", (exec_id,)
                ).fetchone()
                if not row:
                    return None
                d = dict(row)
                v = d.get("result_data")
                if isinstance(v, str):
                    try:
                        d["result_data"] = json.loads(v)
                    except Exception:
                        d["result_data"] = {}
                d["id"] = d["exec_id"]
                return d

    def delete_web_execution(self, exec_id: str) -> bool:
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM web_executions WHERE exec_id = ?", (exec_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    def list_web_executions(self, status=None, keyword=None, test_case=None, page=1, page_size=20):
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM web_executions WHERE 1=1"
                params = []
                if status:
                    sql += " AND status = ?"; params.append(status)
                if test_case:
                    sql += " AND test_case = ?"; params.append(test_case)
                if keyword:
                    sql += " AND (test_case_title LIKE ? OR executed_by_username LIKE ? OR error_message LIKE ?)"
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
                sql += " ORDER BY executed_at DESC"
                rows = conn.execute(sql, params).fetchall()
                items = []
                for r in rows:
                    d = dict(r)
                    v = d.get("result_data")
                    if isinstance(v, str):
                        try:
                            d["result_data"] = json.loads(v)
                        except Exception:
                            d["result_data"] = {}
                    d["id"] = d["exec_id"]
                    items.append(d)
                total = len(items)
                start = (page - 1) * page_size
                end = start + page_size
                return items[start:end], total

    def list_perf_executions(self, status=None, keyword=None, test_case=None, page=1, page_size=20):
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM perf_executions WHERE 1=1"
                params = []
                if status:
                    sql += " AND status = ?"; params.append(status)
                if test_case:
                    sql += " AND test_case = ?"; params.append(test_case)
                if keyword:
                    sql += " AND (test_case_name LIKE ? OR started_by_name LIKE ? OR exec_summary LIKE ?)"
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
                sql += " ORDER BY started_at DESC"
                rows = [self._row_to_record(r, PerfExecutionRecord) for r in conn.execute(sql, params).fetchall()]
                for r in rows:
                    r.id = r.exec_id or r.id
                page_rows, total = self._paginate(rows, page, page_size)
                return page_rows, total

    def get_perf_execution(self, exec_id: str) -> Optional[dict]:
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM perf_executions WHERE exec_id = ?", (exec_id,)
                ).fetchone()
                if not row:
                    return None
                rec = self._row_to_record(row, PerfExecutionRecord)
                rec.id = rec.exec_id or rec.id
                return rec.to_dict()

    # ============================================================
    # 测试执行报告：真实 SQLite 查询
    # ============================================================
    def create_execution(self, data: dict) -> dict:
        """创建一条执行记录及明细，返回 exec_id。"""
        exec_id = data.get("exec_id") or ("exec-" + str(uuid.uuid4())[:8])
        now = datetime.now(timezone.utc).isoformat()
        name = data.get("name", "")
        status = data.get("status", "completed")
        total_cases = int(data.get("total_cases", 0))
        passed_cases = int(data.get("passed_cases", 0))
        failed_cases = int(data.get("failed_cases", 0))
        skipped_cases = int(data.get("skipped_cases", 0))
        duration = float(data.get("duration", 0))
        trigger_type = data.get("trigger_type", "manual")
        summary = data.get("summary", "")
        results = data.get("results", [])
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO executions
                    (exec_id, name, status, total_cases, passed_cases, failed_cases, skipped_cases,
                     duration, trigger_type, summary, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (exec_id, name, status, total_cases, passed_cases, failed_cases, skipped_cases,
                     duration, trigger_type, summary, now, now),
                )
                for r in results:
                    conn.execute(
                        """
                        INSERT INTO execution_results
                        (exec_id, case_id, case_title, status, duration_ms, response_body,
                         assertions, extracted_vars, error_message, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (exec_id,
                         r.get("case_id", ""),
                         r.get("case_title", ""),
                         r.get("status", "pending"),
                         int(r.get("duration_ms", 0)),
                         r.get("response_body", "") if isinstance(r.get("response_body"), str) else json.dumps(r.get("response_body", ""), ensure_ascii=False),
                         json.dumps(r.get("assertions", []), ensure_ascii=False),
                         json.dumps(r.get("extracted_vars", {}), ensure_ascii=False),
                         r.get("error_message", ""),
                         now),
                    )
                conn.commit()
        return {"exec_id": exec_id, "created_at": now}

    def list_executions(self, status=None, keyword=None, page=1, page_size=20):
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM executions WHERE 1=1"
                params = []
                if status:
                    sql += " AND status = ?"; params.append(status)
                if keyword:
                    sql += " AND (name LIKE ? OR summary LIKE ? OR exec_id LIKE ?)"
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
                sql += " ORDER BY created_at DESC"
                rows = conn.execute(sql, params).fetchall()
                items = []
                for r in rows:
                    d = dict(r)
                    d["id"] = d.get("exec_id") or d.get("id")
                    items.append(d)
                page_rows, total = self._paginate(items, page, page_size)
                return page_rows, total

    def get_execution(self, exec_id: str):
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM executions WHERE exec_id = ?", (exec_id,)
                ).fetchone()
                if not row:
                    return None
                d = dict(row)
                d["id"] = d.get("exec_id") or d.get("id")
                return _StubRecord(**d)

    def list_execution_results(self, exec_id: str):
        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM execution_results WHERE exec_id = ? ORDER BY id",
                    (exec_id,),
                ).fetchall()
                results = []
                for r in rows:
                    d = dict(r)
                    for k in ("assertions", "extracted_vars"):
                        v = d.get(k)
                        if isinstance(v, str):
                            try:
                                d[k] = json.loads(v)
                            except Exception:
                                pass
                    results.append(d)
                return results

    # ── 知识库与会话持久化 ──
    def create_knowledge_base(self, name: str, description: str = "", embedding_model: str = "bge-m3", created_by: str = "") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        kb_id = f"kb-{uuid.uuid4().hex[:8]}"
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO knowledge_bases
                    (kb_id, name, description, embedding_model, doc_count, chunk_count, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (kb_id, name, description, embedding_model, 0, 0, created_by, now, now),
                )
                conn.commit()
        return {"kb_id": kb_id, "id": kb_id, "name": name, "description": description,
                "embedding_model": embedding_model, "doc_count": 0, "chunk_count": 0,
                "created_by": created_by, "created_at": now, "updated_at": now}

    def list_knowledge_bases(self, user_id=None) -> list:
        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM knowledge_bases ORDER BY updated_at DESC"
                ).fetchall()
                return [dict(r) for r in rows]

    def get_knowledge_base(self, kb_id: str) -> dict | None:
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM knowledge_bases WHERE kb_id = ?", (kb_id,)
                ).fetchone()
                return dict(row) if row else None

    def create_document(self, kb_id: str, filename: str, file_size: int = 0,
                        file_type: str = "", chunk_count: int = 0) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        doc_id = f"doc-{uuid.uuid4().hex[:8]}"
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO documents
                    (doc_id, kb_id, filename, file_size, file_type, chunk_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (doc_id, kb_id, filename, file_size, file_type, chunk_count, now, now),
                )
                conn.commit()
        return {"doc_id": doc_id, "kb_id": kb_id, "filename": filename,
                "file_size": file_size, "file_type": file_type,
                "chunk_count": chunk_count, "created_at": now, "updated_at": now}

    def get_document(self, doc_id: str) -> dict | None:
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
                ).fetchone()
                return dict(row) if row else None

    def list_documents(self, kb_id: str) -> list:
        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE kb_id = ? ORDER BY created_at DESC",
                    (kb_id,),
                ).fetchall()
                return [dict(r) for r in rows]

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
                conn.commit()
                return cur.rowcount > 0

    def update_knowledge_base_stats(self, kb_id: str, doc_count: int = 0, chunk_count: int = 0) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    """UPDATE knowledge_bases
                       SET doc_count = ?, chunk_count = ?, updated_at = ?
                       WHERE kb_id = ?""",
                    (doc_count, chunk_count, now, kb_id),
                )
                conn.commit()
                return cur.rowcount > 0

    def save_chat_session(self, user_id: str, title: str, mode: str, kb_id: str, session_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                # 注意：chat_sessions 表实际主键列名为 id（与建表语句的 session_id 不一致，
                # 运行时 DB 已使用 id 列），统一用 id 列避免 INSERT/UPDATE 失败导致会话不落库。
                conn.execute(
                    """INSERT INTO chat_sessions
                    (id, user_id, title, mode, kb_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        mode=excluded.mode,
                        kb_id=excluded.kb_id,
                        updated_at=excluded.updated_at""",
                    (session_id, user_id, title, mode, kb_id or "", now, now),
                )
                conn.commit()
        return {"id": session_id, "session_id": session_id, "user_id": user_id,
                "title": title, "mode": mode, "kb_id": kb_id or "",
                "created_at": now, "updated_at": now}

    def save_chat_message(self, session_id: str, role: str, content: str,
                          eval_score: float | None = None, needs_human: bool = False) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO chat_messages
                    (session_id, role, content, eval_score, needs_human, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, role, content, eval_score, 1 if needs_human else 0, now),
                )
                conn.execute(
                    "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                    (now, session_id),
                )
                conn.commit()
        return {"id": conn.lastrowid, "session_id": session_id, "role": role,
                "content": content, "eval_score": eval_score,
                "needs_human": needs_human, "created_at": now}

    def get_chat_sessions(self, user_id: str, mode: str | None = None,
                          kb_id: str | None = None, limit: int = 50) -> list:
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM chat_sessions WHERE user_id = ?"
                params = [user_id]
                if mode:
                    sql += " AND mode = ?"
                    params.append(mode)
                if kb_id:
                    # 兼容早期未保存 kb_id 的知识库会话（kb_id 为空字符串）
                    sql += " AND (kb_id = ? OR kb_id = '' OR kb_id IS NULL)"
                    params.append(kb_id)
                sql += " ORDER BY updated_at DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, params).fetchall()
                result = []
                for r in rows:
                    d = dict(r)
                    # 前端/接口以 session_id 为主键，补充该字段（= id），避免判断为 None
                    d.setdefault("session_id", d.get("id"))
                    result.append(d)
                return result

    def get_chat_messages(self, session_id: str) -> list:
        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC, id ASC",
                    (session_id,),
                ).fetchall()
                return [dict(r) for r in rows]

    def delete_chat_session(self, session_id: str) -> bool:
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
                cur = conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
                conn.commit()
                return cur.rowcount > 0

    def __getattr__(self, name: str):
        """对尚未实现的 Phase 3 存储方法返回空 stub，避免页面 500。"""
        if name.startswith("_"):
            raise AttributeError(name)

        # 明确需要返回 list 的方法（端点直接遍历 / len()）
        _list_methods = {
            "list_knowledge_bases",
            "list_documents",
            "list_models",
            "list_mcp_tools",
            "list_sandboxes",
            "get_chat_sessions",
            "get_chat_messages",
            "list_request_history",
            "list_execution_results",
            "list_quality_standards",
            "get_trace_steps",
            "get_recent_events",
            "get_safety_trend",
            "get_risk_distribution",
        }
        # 需要解包 (rows, total) 的列表方法
        _tuple_list_methods = {
            "list_testcases",
            "list_web_testcases",
            "list_perf_plans",
            "list_executions",
            "list_testsuites",
            "list_templates",
            "list_tasks",
            "list_web_executions",
            "list_perf_executions",
        }
        # 返回 dict 的统计类方法
        _dict_methods = {
            "get_stats",
        }

        def _stub(*args, **kwargs):
            logger.warning(f"[TaskStore] 方法 {name} 尚未实现，返回空 stub")
            if name.startswith("delete_"):
                return False
            if name.startswith("get_") and name.endswith("_stats"):
                return {}
            if name in _dict_methods:
                return {}
            if name in _list_methods:
                return []
            if name in _tuple_list_methods or name.startswith("list_"):
                return [], 0
            # 单条记录类（create/get/update/bulk/save）返回占位对象
            return _StubRecord(id=f"stub-{uuid.uuid4().hex[:8]}")

        return _stub


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
