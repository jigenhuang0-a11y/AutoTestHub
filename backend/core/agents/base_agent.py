"""
Agent 抽象基类

所有专业 Agent 继承此类，统一接口：
- run(prompt, context) → result
- 内置 LLM Router 调用
- 工具调用通过 MCPClient（接入 ToolGateway）
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from core.models.router import get_llm_router, LLMRouter

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent 基类 — 所有专业 Agent 的父类
    
    子类只需实现:
        name: str          — Agent 名称
        description: str   — Agent 描述
        task_type: str     — 使用的 LLM Router 任务类型
        system_prompt: str — 系统提示词
        
        run(prompt, context) → dict — 核心执行逻辑
    
    用法:
        class MyAgent(BaseAgent):
            name = "MyAgent"
            description = "做某事的 Agent"
            task_type = "code_generation"
            system_prompt = "你是一个专业的..."
            
            def run(self, prompt, context=None):
                # 使用 self.ask_llm() 调用模型
                result = self.ask_llm(prompt, context)
                return {"answer": result}
    """
    
    # === 子类必须覆盖的属性 ===
    name: str = "BaseAgent"
    description: str = "Agent 基类"
    task_type: str = "fast_chat"          # LLM Router 任务类型
    system_prompt: str = "你是一个专业的 AI 助手。"
    
    def __init__(self, router: Optional[LLMRouter] = None, use_mcp: bool = True):
        self.router = router or get_llm_router()
        self._tools: dict[str, callable] = {}
        self._mcp_client = None
        self._use_mcp = use_mcp
        if self._use_mcp:
            self._init_mcp_client()
        self._register_tools()
        # 【数据库配置化】从数据库加载自定义 system_prompt，找不到则用硬编码默认值
        self._load_prompt_from_db()

    def _init_mcp_client(self):
        """初始化 MCP 客户端（延迟导入，避免循环引用）"""
        try:
            from core.mcp.client import create_local_client
            self._mcp_client = create_local_client()
            logger.debug(f"[{self.name}] MCP 客户端已初始化")
        except Exception as e:
            logger.warning(f"[{self.name}] MCP 客户端初始化失败，回退到本地工具: {e}")
            self._use_mcp = False
    
    # ============================================================
    # 核心接口
    # ============================================================
    
    @abstractmethod
    def run(self, prompt: str, context: Optional[dict] = None) -> dict:
        """
        执行 Agent 任务
        
        Args:
            prompt: 用户指令
            context: 上下文信息（文档、历史、上游 Agent 输出等）
        
        Returns:
            dict: 执行结果，至少包含 {"status": "success|error", "data": ...}
        """
        ...
    
    # ============================================================
    # 数据库 Prompt 加载（支持无代码部署更新）
    # ============================================================
    
    def _load_prompt_from_db(self):
        """
        从数据库加载自定义 System Prompt
        
        优先级: 数据库 > 代码硬编码
        - 如果 agent_gateway.AgentPromptConfig 表中有记录，使用数据库版本
        - 否则保持当前硬编码的 self.system_prompt
        - 数据库不可用时静默 fallback（不影响正常使用）
        """
        try:
            from agent_gateway.models import AgentPromptConfig
            
            # Agent 子类可以覆盖 _prompt_subtype 来指定使用哪个子类型
            prompt_subtype = getattr(self, '_prompt_subtype', 'default')
            
            db_prompt = AgentPromptConfig.load_prompt(
                agent_name=self.name,
                prompt_subtype=prompt_subtype,
                fallback='',
            )
            if db_prompt:
                logger.info(f"[{self.name}] 从数据库加载 prompt (subtype={prompt_subtype})")
                self.system_prompt = db_prompt
        except Exception:
            # 数据库不可用（如 migrate 前）静默 fallback 到硬编码值
            pass
    
    # ============================================================
    # LLM 调用助手
    # ============================================================
    
    def ask_llm(
        self,
        prompt: str,
        context: Optional[dict] = None,
        stream: bool = False,
        **kwargs
    ) -> str:
        """
        调用 LLM（自动添加 system prompt + context）
        
        Args:
            prompt: 用户消息
            context: 上下文（会追加到 prompt 前）
            stream: 是否流式返回
        """
        messages = self._build_messages(prompt, context)
        
        if stream:
            return self.router.chat_stream(messages, task_type=self.task_type, **kwargs)
        return self.router.chat(messages, task_type=self.task_type, **kwargs)
    
    def _build_messages(self, prompt: str, context: Optional[dict] = None) -> list:
        """构建 LLM 消息列表"""
        system = self.system_prompt
        
        if context:
            ctx_parts = []
            for key, value in context.items():
                ctx_parts.append(f"【{key}】\n{value}")
            system += "\n\n当前上下文:\n" + "\n---\n".join(ctx_parts)
        
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
    
    # ============================================================
    # 工具管理（MCP 优先，本地回退）
    # ============================================================

    def _register_tools(self):
        """子类覆盖此方法注册工具"""
        pass

    def register_tool(self, name: str, func: callable):
        """注册一个工具（本地 + MCP 双注册）"""
        self._tools[name] = func
        logger.debug(f"[{self.name}] 注册工具: {name}")

    def use_tool(self, name: str, *args, **kwargs) -> Any:
        """
        调用已注册的工具

        优先走 MCPClient（含 ToolGateway 权限检查 + 审计），
        MCP 不可用时回退到本地直接调用。

        用法：
            result = self.use_tool("knowledge_search", query="登录接口")
        """
        arguments = kwargs
        if args:
            if args and isinstance(args[0], dict):
                arguments = {**args[0], **kwargs}
            else:
                logger.warning(f"[{self.name}] use_tool 请使用关键字参数调用")

        # 优先走 MCP
        if self._use_mcp and self._mcp_client:
            try:
                self._mcp_user_id = getattr(self, 'user_id', None)
                # 通过 MCP Server 调用（含 Gateway 权限+审计）
                mcp_result = self._mcp_client.server.call_tool(
                    name=name, arguments=arguments,
                    user_id=self._mcp_user_id,
                )
                if mcp_result.get("isError"):
                    error_msg = mcp_result.get("content", [{}])[0].get("text", "Unknown error")
                    # 如果是 "权限拒绝"，直接抛出
                    if "权限拒绝" in error_msg:
                        raise PermissionError(error_msg)
                    raise RuntimeError(error_msg)
                # 解析 MCP 返回的文本为 dict
                content = mcp_result.get("content", [{"text": "{}"}])
                import json
                return json.loads(content[0]["text"])
            except PermissionError:
                raise
            except Exception as e:
                logger.warning(
                    f"[{self.name}] MCP 工具调用失败: {e}，回退到本地调用"
                )

        # 回退：本地直接调用
        if name not in self._tools:
            raise ValueError(f"Agent '{self.name}' 没有工具: {name}")
        try:
            return self._tools[name](**arguments)
        except Exception as e:
            logger.error(f"[{self.name}] 工具 {name} 执行失败: {e}")
            raise

    def list_tools(self) -> list[str]:
        """列出已注册的工具名称"""
        return list(self._tools.keys())

    def get_mcp_tools_for_agent(self) -> list[dict]:
        """获取 OpenAI Function Calling 格式的工具列表（MCP）"""
        if self._mcp_client:
            return self._mcp_client.get_tools_for_agent()
        return []
    
    # ============================================================
    # 辅助方法
    # ============================================================
    
    def _success(self, data: Any, **extra) -> dict:
        return {"status": "success", "data": data, **extra}
    
    def _error(self, message: str, **extra) -> dict:
        logger.error(f"[{self.name}] 错误: {message}")
        return {"status": "error", "error": message, **extra}
    
    def __repr__(self):
        return f"<{self.name} task_type={self.task_type}>"
