from fastapi import APIRouter

from app.api.v1.endpoints import audit, auth, health, llm, mcp, memory, sandbox, tasks, templates, tenants, tool_registry, webhooks, workflow, supervisor

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
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(tenants.router, prefix="/agent/tenants", tags=["tenants"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
