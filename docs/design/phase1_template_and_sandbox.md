# Phase 1.2 + 1.4 设计文档：工作流模板注册表 & 本地代码沙箱

> 设计日期：2026-07-18
> 原则：**设计先行，本地起步**——先在本地 Windows 跑通沙箱、打通模板注册，再上服务器验证。

---

## 一、整体定位

```
┌─────────────────────────────────────────────────────────┐
│                  ai-orchestration-service                │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ Template      │  │ Sandbox      │  │ Harness       │ │
│  │ Registry      │  │ Executor     │  │ (Plan/Orch/  │ │
│  │ (1.2)         │  │ (1.4)        │  │  Verify)      │ │
│  └──────┬───────┘  └──────┬───────┘  └───────────────┘ │
│         │                 │                              │
│         ▼                 ▼                              │
│  ┌──────────────────────────────────────────────────┐   │
│  │                 Django Tool Layer                 │   │
│  │   generator / execution / data_factory / eval     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

- **模板注册表 (1.2)**：让编排服务不再每次靠 LLM 从零"猜"执行计划，而是用预注册的团队模板做种子/约束。
- **本地沙箱 (1.4)**：把 `subprocess.run()` 包装成受控执行器，限制时间、内存、文件访问。

---

## 二、Phase 1.2：团队级工作流模板注册表

### 2.1 要解决什么问题？

**现状问题**：

| 问题 | 现状 | 影响 |
|------|------|------|
| 每次 LLM Plan 输出不可控 | `PLAN_SYSTEM_PROMPT` + LLM 实时生成，无模板约束 | 同一个需求两次运行，LLM 可能拆出不同的步骤 |
| 无团队差异化 | 只有一套硬编码的 `AGENT_REGISTRY` | 团队 A 想用 `generator→data_factory→execution`，团队 B 想用 `data_factory→generator→execution→evaluator`，做不到 |
| 工具注册是字符串映射 | `{"generator": "generate_testcases"}` 无法带参数 schema | Agent 调用时传参靠猜，LLM 生成的 params 可能下游不认 |
| 无版本概念 | 模板改了就是改了 | 无法回滚，无法 A/B 测试不同模板 |

**设计目标**：
1. 每个 team_id 可注册自己的 `WorkflowTemplate`，包含步骤定义、工具绑定、模型偏好
2. Plan 阶段不再纯靠 LLM 自由发挥，而是"模板骨架 + LLM 填充参数"
3. 模板有版本号和状态，支持草稿/发布/回滚
4. 存储层协议化，先在 Redis 存 JSON，以后迁移到 Postgres

### 2.2 数据模型

#### 2.2.1 核心实体

```
WorkflowTemplate
├── template_id: str          # 唯一 ID，如 "default_generator_v1"
├── team_id: str              # 所属团队，"default" 为平台默认模板
├── name: str                 # 模板名称，如 "标准测试生成流水线"
├── version: int              # 版本号，递增
├── status: "draft"|"published"|"deprecated"
├── model_preference: str     # 偏好的模型，如 "deepseek-chat"
├── steps: list[WorkflowStep]
├── metadata: dict            # 扩展字段（描述、标签、负责人等）
└── created_at / updated_at

WorkflowStep
├── order: int                # 执行顺序
├── agent: str                # Agent 名称，对应 AGENT_REGISTRY 的 key
├── prompt_template: str      # 带占位符的 prompt 模板，如 "为 {module} 模块生成 {case_count} 条测试用例"
├── params_schema: dict       # 传给下游 API 的参数 schema（JSON Schema 格式）
├── parallel_group: str|None  # 为空则串行，同组名则并行
├── timeout_seconds: int      # 该步骤的超时时间
├── retry: int                # 失败重试次数
└── depends_on: list[int]     # 依赖的前置步骤（order 列表）
```

#### 2.2.2 Python 数据类定义

```python
# ai-orchestration-service/app/core/template.py

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class TemplateStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


@dataclass
class WorkflowStep:
    order: int
    agent: str                                          # "generator" | "data_factory" | "execution" | "evaluator"
    prompt_template: str                                # "为 {module} 生成 {case_count} 条用例"
    params_schema: dict = field(default_factory=dict)   # JSON Schema
    parallel_group: Optional[str] = None
    timeout_seconds: int = 300
    retry: int = 1
    depends_on: list[int] = field(default_factory=list)


@dataclass
class WorkflowTemplate:
    template_id: str
    team_id: str
    name: str
    version: int = 1
    status: TemplateStatus = TemplateStatus.DRAFT
    model_preference: str = "deepseek-chat"
    steps: list[WorkflowStep] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0
```

#### 2.2.3 预设默认模板

平台预置 3 个模板，开箱即用：

```python
DEFAULT_TEMPLATES = {
    # 模板 1：标准流水线（最常用）
    "standard_pipeline": WorkflowTemplate(
        template_id="standard_pipeline_v1",
        team_id="default",
        name="标准测试生成流水线",
        version=1,
        status=TemplateStatus.PUBLISHED,
        model_preference="deepseek-chat",
        steps=[
            WorkflowStep(order=0, agent="generator", prompt_template="{user_request}", 
                        params_schema={"requirement": "string", "case_count": "int"}),
            WorkflowStep(order=1, agent="data_factory", prompt_template="为上述用例生成测试数据",
                        params_schema={"business_domain": "string", "record_count": "int"},
                        parallel_group="A", depends_on=[]),  # 与 generator 可并行
            WorkflowStep(order=2, agent="execution", prompt_template="执行生成的测试用例",
                        params_schema={"test_case_ids": "list"}),
            WorkflowStep(order=3, agent="evaluator", prompt_template="评估执行结果",
                        params_schema={"execution_id": "int"}),
        ],
    ),

    # 模板 2：快速验证（只生成+执行，跳过数据和评估）
    "quick_validate": WorkflowTemplate(
        template_id="quick_validate_v1",
        team_id="default",
        name="快速验证流水线",
        version=1,
        status=TemplateStatus.PUBLISHED,
        model_preference="qwen-turbo",
        steps=[
            WorkflowStep(order=0, agent="generator", prompt_template="{user_request}",
                        params_schema={"requirement": "string", "case_count": "int"}),
            WorkflowStep(order=1, agent="execution", prompt_template="执行生成的测试用例",
                        params_schema={"test_case_ids": "list"}),
        ],
    ),

    # 模板 3：评测优先（先生成数据再生成用例，最后执行+评估）
    "eval_first": WorkflowTemplate(
        template_id="eval_first_v1",
        team_id="default",
        name="评测优先流水线",
        version=1,
        status=TemplateStatus.PUBLISHED,
        model_preference="deepseek-chat",
        steps=[
            WorkflowStep(order=0, agent="data_factory", prompt_template="为 {module} 生成测试数据",
                        params_schema={"business_domain": "string", "record_count": "int"}),
            WorkflowStep(order=1, agent="generator", prompt_template="{user_request}",
                        params_schema={"requirement": "string", "case_count": "int"}),
            WorkflowStep(order=2, agent="execution", prompt_template="执行生成的测试用例",
                        params_schema={"test_case_ids": "list"}),
            WorkflowStep(order=3, agent="evaluator", prompt_template="评估执行结果并输出报告",
                        params_schema={"execution_id": "int"}),
        ],
    ),
}
```

### 2.3 存储层设计

**Phase 1 阶段**：用 Redis Hash 存 JSON，关键词是 `template:{team_id}:{template_id}`。

```
Key:   template:{team_id}:{template_id}
Value: WorkflowTemplate 的 JSON 序列化
TTL: 无（长存）

Key:   template:index:{team_id}
Value: ["standard_pipeline_v1", "quick_validate_v1", ...]  # 该团队的所有模板 ID 列表
```

**为什么先 Redis 不直接上 Postgres？**
- Phase 1 重点是跑通流程，不是做完整的模板管理系统
- Redis 已有的基础设施，零额外成本
- JSON 格式天然适合 dataclass 序列化/反序列化
- 以后迁移 Postgres：数据模型不变，换存储层实现即可

**存储层抽象**（协议化，方便以后切 Postgres）：

```python
# ai-orchestration-service/app/core/template_store.py

class TemplateStore(ABC):
    """模板存储抽象"""

    @abstractmethod
    async def get(self, team_id: str, template_id: str) -> Optional[WorkflowTemplate]: ...

    @abstractmethod
    async def list(self, team_id: str) -> list[WorkflowTemplate]: ...

    @abstractmethod
    async def save(self, template: WorkflowTemplate) -> bool: ...

    @abstractmethod
    async def delete(self, team_id: str, template_id: str) -> bool: ...

    @abstractmethod
    async def get_default(self, team_id: str) -> Optional[WorkflowTemplate]: ...
```

- `RedisTemplateStore`：当前实现
- `MemoryTemplateStore`：回退兜底，`DEFAULT_TEMPLATES` 常驻内存
- 以后 `PostgresTemplateStore`：切存储层不换业务代码

### 2.4 与现有 Harness 的集成点

当前 `plan_node()` 的核心逻辑是：

```
用户需求 → LLM（PLAN_SYSTEM_PROMPT）→ JSON 数组 → 执行
```

**改后**变成：

```
用户需求 → 查 team_id 的默认模板
         ├── 有模板 → 模板骨架 + LLM 填充参数 → JSON 数组 → 执行
         └── 无模板 → LLM 自由生成（保留兼容）→ JSON 数组 → 执行
```

修改 `plan_node()` 的改动很小——只换 prompt 构造方式：

```python
def plan_node(state: dict) -> dict:
    team_id = state.get("team_id", "default")
    
    # 1. 查模板
    template = get_template(team_id)
    
    if template:
        # 2. 有模板：让 LLM 在模板约束下填充参数
        plan = _fill_template_with_llm(template, state["user_request"])
    else:
        # 3. 无模板：旧逻辑，LLM 自由生成
        plan = _llm_free_plan(state["user_request"])
    
    # 剩下的逻辑不变...
```

### 2.5 API 设计

在 `ai-orchestration-service` 新增模板管理端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/templates/{team_id}` | 列出团队所有模板 |
| `GET` | `/api/v1/templates/{team_id}/{template_id}` | 获取单个模板 |
| `POST` | `/api/v1/templates/{team_id}` | 创建新模板 |
| `PUT` | `/api/v1/templates/{team_id}/{template_id}` | 更新模板（自动版本+1） |
| `DELETE` | `/api/v1/templates/{team_id}/{template_id}` | 删除模板 |
| `POST` | `/api/v1/templates/{team_id}/{template_id}/publish` | 发布模板 |

**请求示例**：

```json
POST /api/v1/templates/team_alpha
{
  "name": "安全测试流水线",
  "model_preference": "deepseek-chat",
  "steps": [
    {
      "order": 0,
      "agent": "generator",
      "prompt_template": "为 {module} 生成 {case_count} 条安全测试用例",
      "params_schema": {
        "module": {"type": "string", "required": true},
        "case_count": {"type": "integer", "default": 10}
      },
      "parallel_group": "A"
    },
    {
      "order": 1,
      "agent": "execution",
      "prompt_template": "执行安全测试用例",
      "params_schema": {},
      "timeout_seconds": 600,
      "retry": 2
    }
  ]
}
```

### 2.6 一句话总结

> "模板不是替代 LLM Plan，而是给 LLM Plan 一个可信的骨架。LLM 负责填入具体参数，模板负责保证流程一致性。团队 A 的安全测试流水线和团队 B 的快速验证流水线各走各的，互不干扰。"

---

## 三、Phase 1.4：本地代码沙箱

### 3.1 要解决什么问题？

**现状风险**（来自代码探索结果）：

| 风险点 | 代码位置 | 影响 |
|--------|----------|------|
| AI 生成的测试代码直接子进程执行 | `backend/execution/engine.py:991` `subprocess.run(cmd, ...)` | 恶意代码能删文件、读密钥、挖矿 |
| `shell=True` 的命令注入风险 | `backend/execution/views.py:596,718` | `allure generate` 用了 `shell=True` |
| 无内存/CPU 限制 | 全部 subprocess 调用 | 一个死循环把 CPU 打满，服务器挂掉 |
| 无超时兜底 | `playwright_engine.py` 120s，但无全局上限 | AI 生成的代码死循环，进程永不退出 |
| 文件系统无限制 | 写临时文件到 `project_root`，可随意读写 | 脏数据污染、覆盖关键文件 |

**设计目标（本地起步）**：
1. 把 `subprocess.run()` 包装成 `SandboxExecutor.execute()`
2. 子进程执行 + 超时 + 资源限制（Windows 兼容）
3. 只读文件系统视图（用临时目录拷贝隔离）
4. 执行后自动清理
5. 本地 Windows 可跑，不需要 Docker

### 3.2 架构设计

```
┌─────────────────────────────────────────────────────┐
│                   SandboxExecutor                    │
│                                                     │
│  execute(code: str, config: SandboxConfig) → Result  │
│                                                     │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │ FileJail │  │Resource   │  │ ProcessManager   │ │
│  │          │  │Limiter    │  │                  │ │
│  │ 创建临时  │  │ 内存上限  │  │ subprocess.Popen │ │
│  │ 目录     │  │ CPU 限制  │  │ + 超时 watchdog  │ │
│  │ 拷贝只读  │  │ 进程数限制│  │ + psutil 监控    │ │
│  │ 文件     │  │           │  │                  │ │
│  └──────────┘  └───────────┘  └──────────────────┘ │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │              ResultCollector                   │   │
│  │  stdout / stderr / exit_code / duration /      │   │
│  │  peak_memory / killed_by_timeout               │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 3.3 数据模型

```python
# ai-orchestration-service/app/core/sandbox.py

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class SandboxStatus(str, Enum):
    SUCCESS = "success"           # 正常退出，exit_code=0
    TIMEOUT = "timeout"           # 超时被 kill
    MEMORY_EXCEEDED = "memory_exceeded"  # 内存超限被 kill
    RUNTIME_ERROR = "runtime_error"      # 正常退出但 exit_code≠0
    SYSTEM_ERROR = "system_error"        # 沙箱自身异常（无法启动等）


@dataclass
class SandboxConfig:
    """沙箱执行配置"""
    # 资源限制
    timeout_seconds: int = 300          # 执行超时（秒）
    max_memory_mb: int = 512            # 最大内存（MB），0=不限制
    max_cpu_percent: int = 80           # 最大 CPU 使用率（%），仅 Linux
    max_processes: int = 5              # 最大子进程数

    # 文件系统
    work_dir: Optional[str] = None      # 工作目录，None=自动创建临时目录
    read_only_paths: list[str] = field(default_factory=list)  # 只读挂载路径
    allowed_write_paths: list[str] = field(default_factory=lambda: ["/tmp", "."])
    allow_network: bool = True          # 测试用例需要发 HTTP 请求

    # 环境变量
    env_whitelist: list[str] = field(default_factory=lambda: ["PATH", "PYTHONPATH", "HOME", "TEMP", "TMP"])
    inherit_env: bool = True            # 是否继承当前进程环境变量

    # 清理
    cleanup_after: bool = True          # 执行完是否删临时目录


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    status: SandboxStatus
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    error_message: str = ""
```

### 3.4 核心实现策略（Windows 兼容）

#### 3.4.1 FileJail：文件系统隔离

**Windows 本地策略**（不用 Docker、不用 chroot）：

```
1. 创建临时目录：  C:/Users/xxx/AppData/Local/Temp/sandbox_{uuid}/
2. 把需只读的文件 copy 进去（如 pytest 测试文件、依赖配置）
3. 子进程 cwd 设为该临时目录
4. 执行完毕自动 shutil.rmtree 删除
```

```python
class FileJail:
    """文件系统隔离——本地版用临时目录拷贝，服务器版可升级为 Docker volume"""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self.temp_dir = None

    def setup(self) -> str:
        """创建隔离文件系统，返回工作目录路径"""
        import uuid, shutil
        self.temp_dir = os.path.join(tempfile.gettempdir(), f"sandbox_{uuid.uuid4().hex[:8]}")
        os.makedirs(self.temp_dir, exist_ok=True)

        # 拷贝只读文件
        for src in self.config.read_only_paths:
            if os.path.isfile(src):
                shutil.copy2(src, self.temp_dir)
            elif os.path.isdir(src):
                dest = os.path.join(self.temp_dir, os.path.basename(src))
                shutil.copytree(src, dest)

        return self.temp_dir

    def cleanup(self):
        """删除临时目录"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
```

#### 3.4.2 ResourceLimiter：资源限制

**Windows 实现策略**：Windows 不像 Linux 有 cgroups，但可以用 `psutil` + watchdog 线程做**监控 + 超限杀进程**：

```python
class ResourceLimiter:
    """资源限制器——本地版用 psutil 监控，服务器版可升级为 cgroups/Docker"""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._stop_event = threading.Event()

    def monitor(self, pid: int):
        """在后台线程监控进程资源，超限时 kill"""
        try:
            proc = psutil.Process(pid)
            while not self._stop_event.is_set():
                # 检查内存
                mem_mb = proc.memory_info().rss / 1024 / 1024
                if self.config.max_memory_mb > 0 and mem_mb > self.config.max_memory_mb:
                    proc.kill()
                    logger.warning(f"[Sandbox] 内存超限 {mem_mb:.1f}MB > {self.config.max_memory_mb}MB，已终止")
                    break

                # 检查子进程数
                children = proc.children(recursive=True)
                if len(children) > self.config.max_processes:
                    proc.kill()
                    logger.warning(f"[Sandbox] 子进程数超限 {len(children)} > {self.config.max_processes}，已终止")
                    break

                self._stop_event.wait(timeout=0.5)  # 每 0.5s 检查一次
        except psutil.NoSuchProcess:
            pass  # 进程已退出

    def stop(self):
        self._stop_event.set()
```

#### 3.4.3 ProcessManager：进程生命周期管理

```python
class ProcessManager:
    """进程管理器——subprocess + timeout watchdog"""

    def __init__(self, config: SandboxConfig):
        self.config = config

    def run(self, cmd: list[str], cwd: str, env: dict) -> SandboxResult:
        """执行命令并监控"""
        import time as time_module
        start = time_module.time()

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # 启动资源监控
            limiter = ResourceLimiter(self.config)
            monitor_thread = threading.Thread(target=limiter.monitor, args=(proc.pid,))
            monitor_thread.start()

            try:
                stdout, stderr = proc.communicate(timeout=self.config.timeout_seconds)
                status = SandboxStatus.SUCCESS if proc.returncode == 0 else SandboxStatus.RUNTIME_ERROR
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                status = SandboxStatus.TIMEOUT

            limiter.stop()
            monitor_thread.join(timeout=2)

            duration = time_module.time() - start
            peak_mem = 0.0
            try:
                peak_mem = psutil.Process(proc.pid).memory_info().rss / 1024 / 1024
            except Exception:
                pass

            return SandboxResult(
                status=status,
                exit_code=proc.returncode,
                stdout=stdout or "",
                stderr=stderr or "",
                duration_seconds=duration,
                peak_memory_mb=peak_mem,
            )

        except Exception as e:
            return SandboxResult(
                status=SandboxStatus.SYSTEM_ERROR,
                error_message=str(e),
                duration_seconds=time_module.time() - start,
            )
```

### 3.5 与 Django 执行引擎的集成

**改动策略：不改原有逻辑，加一层包装。**

原代码：
```python
# backend/execution/engine.py:991
result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env, cwd=self.project_root)
```

**方案 A（Phase 1 推荐）：最小改动——在 Django 端引入 SandboxExecutor**

```python
# backend/execution/sandbox_adapter.py  （新增）
from ai_orchestration_client import SandboxExecutor, SandboxConfig

def run_test_in_sandbox(cmd: list[str], test_file: str, config: dict):
    """把原有的 subprocess.run 替换为沙箱执行"""
    sandbox_config = SandboxConfig(
        timeout_seconds=config.get("timeout", 300),
        max_memory_mb=config.get("max_memory_mb", 512),
        read_only_paths=[test_file],  # 测试文件只读
        allow_network=True,
        cleanup_after=True,
    )
    executor = SandboxExecutor(sandbox_config)
    result = executor.execute(
        code=Path(test_file).read_text(),
        filename=os.path.basename(test_file),
    )
    return result
```

然后在 `TestExecutionEngine._run_pytest()` 中：
```python
# 改前
result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, ...)

# 改后  
sandbox_result = run_test_in_sandbox(cmd, test_file=str(test_file_path), config={
    "timeout": 600,
    "max_memory_mb": 1024,
})
```

**方案 B（Phase 3+ 升级）：沙箱作为独立 gRPC 服务**

```
编排服务 ──gRPC──▶ Sandbox Service ──Docker──▶ 隔离容器执行
```
本地先跑通方案 A，服务器上用方案 B 替换。

### 3.6 安全边界清单

| 维度 | 本地版（Phase 1） | 服务器版（Phase 2+） |
|------|-------------------|----------------------|
| 进程隔离 | `subprocess.Popen` 子进程 | Docker 容器 / gVisor |
| 文件隔离 | 临时目录拷贝 + 只读标记 | Docker volume + read-only mount |
| 内存限制 | psutil 监控 + 超限 kill | cgroups memory limit |
| CPU 限制 | psutil 监控 | cgroups cpu shares |
| 网络隔离 | 允许（测试需要） | 可选，白名单域名 |
| 超时 | `subprocess.communicate(timeout=...)` | 同 + Docker stop |
| 环境变量 | 白名单过滤后继承 | 完全隔离，只传必要变量 |
| 清理 | `shutil.rmtree` | Docker rm --force |

### 3.7 文件清单（Phase 1.4 产出）

```
ai-orchestration-service/app/core/
├── sandbox.py              # SandboxConfig, SandboxResult, SandboxExecutor
├── sandbox_file_jail.py    # FileJail（文件隔离）
├── sandbox_resource.py     # ResourceLimiter（资源限制）
└── sandbox_process.py      # ProcessManager（进程管理）

backend/execution/
└── sandbox_adapter.py      # Django 侧适配器，替换裸 subprocess

ai-orchestration-service/tests/
└── test_sandbox.py         # 沙箱单元测试
```

---

## 四、文件清单（Phase 1.2 产出）

```
ai-orchestration-service/app/core/
├── template.py             # WorkflowTemplate, WorkflowStep 数据模型
└── template_store.py       # TemplateStore(ABC), RedisTemplateStore, MemoryTemplateStore

ai-orchestration-service/app/api/v1/endpoints/
└── templates.py            # 模板 CRUD API

ai-orchestration-service/app/schemas/
└── template.py             # Pydantic 请求/响应模型

ai-orchestration-service/tests/
└── test_template.py        # 模板注册表单元测试
```

---

## 五、本地开发→服务器部署路线

```
Phase 1（当前）:
  本地 Windows
  ├── 1.2 模板注册表：MemoryTemplateStore → RedisTemplateStore
  └── 1.4 本地沙箱：   subprocess + psutil + 临时目录

Phase 2（7月底部署）:
  服务器 Linux
  ├── 模板存储切 Postgres（Agent 版本管理 + A/B 测试）
  └── 沙箱切 Docker（cgroups 精确限制 + 网络隔离）

Phase 3（8月）:
  ├── 沙箱 gRPC 独立服务
  └── 模板市场（团队间分享模板）
```

---

## 六、面试话术

**模板注册表**：
> "编排服务不只是每次让 LLM 自由发挥，我们设计了团队级工作流模板注册表。每个团队可以注册自己的流水线模板——定义步骤顺序、Agent 选择、参数 schema 和模型偏好。LLM Plan 阶段不再从零开始，而是在模板骨架的约束下填充参数，保证流程一致性的同时保留了灵活性。"

**本地沙箱**：
> "AI 生成的测试代码不能直接在宿主机上跑。我们做了一层沙箱执行器，本地版用 subprocess + psutil 做进程隔离和资源限制，文件操作限制在临时目录里。服务器上可以无缝升级到 Docker 容器隔离。关键设计是本地和服务器用同一套 SandboxConfig/SandboxResult 接口，换底层实现不改业务代码。"
