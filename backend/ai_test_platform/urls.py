"""URL configuration for ai_test_platform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# ============================================================
# 修复：DRF DefaultRouter 重复注册 drf_format_suffix 转换器
# 多个 DefaultRouter 实例化时都会调用 format_suffix_patterns，
# 每次都会尝试注册 drf_format_suffix，导致第二次注册抛 ValueError
# ============================================================
import django.urls
_original_register_converter = django.urls.register_converter

def _safe_register_converter(converter, type_name):
    try:
        _original_register_converter(converter, type_name)
    except ValueError as e:
        if type_name == 'drf_format_suffix':
            return  # 忽略重复注册
        raise e

django.urls.register_converter = _safe_register_converter

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/testcases/', include('testcases.urls')),
    path('api/web-testcases/', include('web_testcases.urls')),
    path('api/execution/', include('execution.urls')),
    path('api/executions/', include('execution.urls')),  # 兼容旧前端构建
    path('api/reports/', include('reports.urls')),
    path('api/testsuites/', include('testsuites.urls')),
    path('api/knowledge/', include('knowledge_base.urls')),
    path('api/data-factory/', include('data_factory.urls')),
    path('api/quality-checker/', include('quality_checker.urls')),
    path('api/ai-evaluator/', include('ai_evaluator.urls')),
    path('api/agent/', include('agent_gateway.urls')),
    path('api/mcp/', include('agent_gateway.mcp_urls')),
    path('api/performance/', include('performance.urls')),
    path('api/demo/', include('demo_api.urls')),
    # SPA catch-all: 排除 api/admin/media/assets/static 路径，返回 index.html
    re_path(r'^(?!api/|admin/|media/|assets/|static/).*$', TemplateView.as_view(template_name='index.html')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
