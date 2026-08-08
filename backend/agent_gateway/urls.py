from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, self_healing_views
from .mcp_urls import urlpatterns as mcp_urlpatterns

router = DefaultRouter()
router.register(r'tasks', views.AgentTaskViewSet, basename='agent-task')

urlpatterns = [
    # ── DRF 路由 ──
    path('', include(router.urls)),
    # ── 自愈 API ──
    path('self-healing/analyze/', self_healing_views.analyze_error, name='self-healing-analyze'),
    path('self-healing/heal/', self_healing_views.heal_step, name='self-healing-heal'),
    path('self-healing/execute/', self_healing_views.execute_healing, name='self-healing-execute'),
    path('self-healing/stats/', self_healing_views.healing_stats, name='self-healing-stats'),
    path('self-healing/history/', self_healing_views.healing_history, name='self-healing-history'),
    path('self-healing/classify-batch/', self_healing_views.classify_batch, name='self-healing-classify-batch'),
    # ── MCP 工具网关（TODO：后续可拆到 agent-harness 底座，平台仅保留透传）──
    *mcp_urlpatterns,
    # ── 审计大屏代理 → agent-harness /api/v1/audit/ ──
    path('audit/<path:subpath>', views.audit_proxy, name='audit-proxy'),
    path('audit/', views.audit_proxy, name='audit-proxy-root'),
]
