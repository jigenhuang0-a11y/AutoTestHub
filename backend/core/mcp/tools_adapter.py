"""
MCP 工具适配器 — 将现有 BaseTool 适配为 MCP 标准工具

将项目的 8 个工具 (BaseTool 子类) 无缝注册到 MCP Server
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# MCP 工具 Schema 生成


def _build_input_schema(tool_name: str, description_hint: str = "") -> dict:
    """
    根据工具类型构建 JSON Schema

    每个工具的参数 Schema 基于其实际参数定义
    """
    schemas = {
        "testcase_search": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "status": {"type": "string", "enum": ["draft", "active", "archived", "all"], "default": "all"},
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3", "all"], "default": "all"},
                "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                "offset": {"type": "integer", "default": 0},
            },
            "required": [],
        },
        "testcase_create": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "用例标题"},
                "description": {"type": "string", "description": "用例描述"},
                "steps": {"type": "array", "items": {"type": "string"}, "description": "测试步骤"},
                "expected_result": {"type": "string", "description": "预期结果"},
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"], "default": "P2"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "标签"},
            },
            "required": ["title"],
        },
        "testcase_update": {
            "type": "object",
            "properties": {
                "case_id": {"type": "integer", "description": "用例 ID"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "status": {"type": "string", "enum": ["draft", "active", "archived"]},
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
            },
            "required": ["case_id"],
        },
        "testcase_delete": {
            "type": "object",
            "properties": {
                "case_id": {"type": "integer", "description": "用例 ID"},
                "soft": {"type": "boolean", "default": True, "description": "是否软删除"},
            },
            "required": ["case_id"],
        },
        "execution_run": {
            "type": "object",
            "properties": {
                "suite_id": {"type": "integer", "description": "测试套件 ID"},
                "test_case_ids": {"type": "array", "items": {"type": "integer"}, "description": "用例 ID 列表"},
                "environment": {"type": "string", "enum": ["dev", "test", "staging", "prod"], "default": "test"},
                "variables": {"type": "object", "description": "执行变量"},
            },
            "required": [],
        },
        "execution_status": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "integer", "description": "执行记录 ID"},
            },
            "required": ["execution_id"],
        },
        "execution_logs": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "integer", "description": "执行记录 ID"},
                "case_index": {"type": "integer", "description": "用例索引"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["execution_id"],
        },
        "data_generate": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "enum": ["order", "user", "logistics", "after_sales", "custom"], "description": "业务域"},
                "count": {"type": "integer", "default": 10, "minimum": 1, "maximum": 1000},
                "fields": {"type": "array", "items": {"type": "object"}, "description": "自定义字段"},
                "strategy": {"type": "string", "enum": ["smart", "boundary", "random", "template"], "default": "smart"},
            },
            "required": [],
        },
        "data_query": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "integer", "description": "数据集 ID"},
                "limit": {"type": "integer", "default": 20},
                "filters": {"type": "object", "description": "过滤条件"},
            },
            "required": [],
        },
        "knowledge_search": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询"},
                "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                "kb_id": {"type": "integer", "description": "知识库 ID, 为空则搜索所有"},
            },
            "required": ["query"],
        },
        "knowledge_upload": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"},
                "kb_id": {"type": "integer", "description": "目标知识库 ID"},
                "title": {"type": "string", "description": "文档标题"},
            },
            "required": ["file_path"],
        },
        "report_generate": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "integer", "description": "执行记录 ID"},
                "format": {"type": "string", "enum": ["html", "pdf", "json", "allure"], "default": "html"},
                "include_logs": {"type": "boolean", "default": True},
            },
            "required": ["execution_id"],
        },
        "evaluate_run": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "integer", "description": "执行记录 ID"},
                "dimensions": {"type": "array", "items": {"type": "string"}, "description": "评估维度"},
            },
            "required": ["execution_id"],
        },
    }

    return schemas.get(tool_name, {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": description_hint or "查询参数"},
        },
        "required": [],
    })


# ============================================================
# 工具处理函数工厂
# ============================================================

def _make_handler(tool_class_path: str, user_id: int = None, action: str = None):
    """创建工具调用处理函数"""

    def handler(**kwargs):
        try:
            # 动态导入
            module_path, class_name = tool_class_path.rsplit(".", 1)
            import importlib
            mod = importlib.import_module(module_path)
            tool_cls = getattr(mod, class_name)

            # 实例化
            tool = tool_cls(user_id=user_id) if user_id else tool_cls()

            # 调用 — 统一使用 execute 方法，并将工具名作为 action 透传
            # 方便一个类对应多个 MCP 工具时做内部分发
            result = tool.execute(action=action, **kwargs)
            return result
        except Exception as e:
            logger.exception(f"[MCP.Adapter] 工具执行失败: {tool_class_path}")
            return {"error": str(e)}

    return handler


# ============================================================
# 工具注册
# ============================================================

def register_all_tools(server, user_id: int = None) -> int:
    """
    将所有项目工具注册到 MCP Server

    Args:
        server: MCPServer 实例
        user_id: 用户 ID (用于多租户隔离)

    Returns:
        注册的工具数量
    """
    tools_to_register = [
        # ===== 测试用例工具 =====
        ("testcase_search", "搜索测试用例，支持关键词、状态、优先级过滤",
         "testcase_search", "core.tools.testcase_storage.TestCaseStorageTool",
         "testcase"),

        ("testcase_create", "创建新的测试用例",
         "testcase_create", "core.tools.testcase_storage.TestCaseStorageTool",
         "testcase"),

        ("testcase_batch_save", "批量保存 AI 生成的测试用例到数据库",
         "testcase_create", "core.tools.testcase_storage.TestCaseStorageTool",
         "testcase"),

        # ===== 执行工具 =====
        ("execution_run", "执行测试套件或用例集",
         "execution_run", "execution.engine.TestExecutionEngine",
         "execution"),

        ("execution_status", "查询执行记录的状态和结果",
         "execution_status", "core.tools.execution_storage.ExecutionStorageTool",
         "execution"),

        # ===== 数据工厂工具 =====
        ("data_generate", "AI 智能生成测试数据（订单/用户/物流等）",
         "data_generate", "core.tools.data_factory_storage.DataFactoryStorageTool",
         "data"),

        # ===== 知识库工具 =====
        ("knowledge_search", "从知识库中语义搜索相关内容",
         "knowledge_search", "core.tools.knowledge_search.KnowledgeSearchTool",
         "knowledge"),

        # ===== 报告工具 =====
        ("report_generate", "生成测试报告（HTML/PDF/Allure）",
         "report_generate", "core.tools.allure_reporter.AllureReporterTool",
         "report"),

        # ===== 评估工具 =====
        ("evaluate_run", "AI 评估执行结果并生成质量报告",
         "evaluate_run", "core.tools.evaluation_storage.EvaluationStorageTool",
         "report"),

        # ===== 通用工具 =====
        ("system_health", "检查系统各组件健康状态",
         "system_health", "core.models.router.LLMRouter",
         "system"),
    ]

    count = 0
    for name, description, schema_key, class_path, category in tools_to_register:
        try:
            schema = _build_input_schema(schema_key, description)
            tool_handler = _make_handler(class_path, user_id, schema_key)

            # 包装 handler 以处理参数名适配
            def make_wrapped_handler(h, tool_name):
                def wrapped(**kwargs):
                    result = h(**kwargs)

                    # 统一返回格式
                    if isinstance(result, dict) and "status" not in result:
                        result["status"] = "success"
                    return result
                return wrapped

            server.register_tool(
                name=name,
                description=description,
                input_schema=schema,
                handler=make_wrapped_handler(tool_handler, name),
                category=category,
            )
            count += 1
        except Exception as e:
            logger.warning(f"[MCP.Adapter] 跳过工具 {name}: {e}")

    logger.info(f"[MCP.Adapter] 成功注册 {count} 个工具到 MCP Server")
    return count


def adapt_tool_to_mcp(tool_instance, server: "MCPServer", category: str = "custom") -> Optional[str]:
    """
    将单个 BaseTool 实例适配并注册到 MCP Server

    Args:
        tool_instance: BaseTool 子类实例
        server: MCPServer 实例
        category: 工具分类

    Returns:
        注册的工具名
    """
    try:
        schema = {
            "type": "object",
            "properties": tool_instance._get_parameters_schema() if hasattr(tool_instance, "_get_parameters_schema") else {},
            "required": tool_instance._get_required_params() if hasattr(tool_instance, "_get_required_params") else [],
        }

        def handler(**kwargs):
            return tool_instance.run(**kwargs)

        server.register_tool(
            name=tool_instance.name,
            description=tool_instance.description,
            input_schema=schema,
            handler=handler,
            category=category,
        )
        return tool_instance.name
    except Exception as e:
        logger.warning(f"[MCP.Adapter] 适配工具失败 {type(tool_instance).__name__}: {e}")
        return None
