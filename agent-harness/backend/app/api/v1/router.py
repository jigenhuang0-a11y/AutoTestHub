from fastapi import APIRouter

from app.api.v1.endpoints import (audit, auth, health, llm, mcp, memory, sandbox,
    tasks, team, templates, tenants, tool_registry, webhooks, workflow, supervisor,
    environments, knowledge, testcases, execution, quality_checker, testsuites,
    data_factory, web_testcases, performance, reports, ai_base)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(tasks.router, prefix="/agent/tasks", tags=["tasks"])
api_router.include_router(workflow.router, prefix="/workflow", tags=["workflow"])
api_router.include_router(supervisor.router, prefix="/supervisor", tags=["supervisor"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(tool_registry.router, prefix="/tools", tags=["tools"])
api_router.include_router(sandbox.router, prefix="/agent/sandbox", tags=["sandbox"])
api_router.include_router(environments.router, prefix="/agent/environments", tags=["environments"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(tenants.router, prefix="/agent/tenants", tags=["tenants"])
api_router.include_router(team.router, prefix="/team", tags=["team-orchestration"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge-rag"])

# Phase 3 迁移：测试平台模块（接口测试/执行/需求评审/套件/数据工厂/Web/性能/报告）
# 注意：各 router 自身已带完整前缀（如 /testcases），这里 include 时不再额外加前缀，避免重复。
api_router.include_router(testcases.router, tags=["testcases"])
api_router.include_router(execution.router, tags=["execution"])
api_router.include_router(quality_checker.router, tags=["quality-checker"])
api_router.include_router(testsuites.router, tags=["testsuites"])
api_router.include_router(data_factory.router, tags=["data-factory"])
api_router.include_router(web_testcases.router, tags=["web-testcases"])
api_router.include_router(performance.router, tags=["performance"])
api_router.include_router(reports.router, tags=["reports"])

# AI 底座 / 模型配置（供测试模块选择模型、走真实 LLM）
api_router.include_router(ai_base.router, tags=["ai-base"])
