"""
Agent 层 — 测试业务 Agent 工具集（通过 MCP 注册到底座）

目录结构:
- base_agent.py      : Agent 抽象基类
- plan_agent.py      : 需求分析/规划 Agent
- testcase_gen_agent.py: 用例生成 Agent
- data_factory_agent.py: 数据工厂 Agent
- execution_agent.py : 执行引擎 Agent
- evaluator_agent.py : AI 评估 Agent
- knowledge_agent.py : 知识库 RAG Agent
"""
from .base_agent import BaseAgent
from .plan_agent import PlanAgent, create_planner
from .testcase_gen_agent import TestCaseGeneratorAgent, create_generator
from .data_factory_agent import DataFactoryAgent, create_data_factory
from .execution_agent import ExecutionEngineAgent, create_execution_agent
from .evaluator_agent import EvaluatorAgent, create_evaluator
from .knowledge_agent import KnowledgeAgent, create_knowledge_agent

__all__ = [
    'BaseAgent',
    'PlanAgent', 'create_planner',
    'TestCaseGeneratorAgent', 'create_generator',
    'DataFactoryAgent', 'create_data_factory',
    'ExecutionEngineAgent', 'create_execution_agent',
    'EvaluatorAgent', 'create_evaluator',
    'KnowledgeAgent', 'create_knowledge_agent',
]
