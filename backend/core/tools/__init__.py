"""
工具基类 — Agent 可调用的工具抽象
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    工具基类
    
    所有 Agent 工具继承此类，实现统一的：
    - 输入校验
    - 异常处理
    - 日志记录
    
    用法:
        class CalculatorTool(BaseTool):
            name = "calculator"
            description = "执行数学计算"
            
            def execute(self, expression: str) -> dict:
                result = eval(expression)
                return {"result": result}
    """
    
    name: str = "base_tool"
    description: str = "基础工具"
    
    @abstractmethod
    def execute(self, **kwargs) -> dict:
        """执行工具逻辑，子类必须实现"""
        ...
    
    def run(self, **kwargs) -> dict:
        """带异常处理的执行包装"""
        try:
            logger.debug(f"[Tool:{self.name}] 执行，参数: {kwargs}")
            result = self.execute(**kwargs)
            logger.debug(f"[Tool:{self.name}] 完成")
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"[Tool:{self.name}] 失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def to_openai_function(self) -> dict:
        """转为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self._get_parameters_schema(),
                    "required": self._get_required_params(),
                }
            }
        }
    
    def _get_parameters_schema(self) -> dict:
        """子类覆盖：返回参数 schema"""
        return {}
    
    def _get_required_params(self) -> list:
        """子类覆盖：返回必填参数列表"""
        return []
    
    def __repr__(self):
        return f"<Tool:'{self.name}'>"


from .knowledge_search import KnowledgeSearchTool, get_knowledge_tool
from .testcase_storage import TestCaseStorageTool, TestCaseInput, SaveResult
from .data_factory_storage import DataFactoryStorageTool, DatasetCreateResult
from .variable_binding import VariableBindingTool
from .execution_storage import ExecutionStorageTool, ExecutionCreateResult
from .allure_reporter import AllureReporterTool
from .evaluation_storage import EvaluationStorageTool
from .milvus_store import MilvusStore, get_milvus_store

__all__ = [
    "BaseTool",
    "KnowledgeSearchTool",
    "get_knowledge_tool",
    "TestCaseStorageTool",
    "TestCaseInput",
    "SaveResult",
    "DataFactoryStorageTool",
    "DatasetCreateResult",
    "VariableBindingTool",
    "ExecutionStorageTool",
    "ExecutionCreateResult",
    "AllureReporterTool",
    "EvaluationStorageTool",
    "MilvusStore", "get_milvus_store",
]
