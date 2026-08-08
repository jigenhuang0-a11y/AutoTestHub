import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AgentGatewayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agent_gateway'
    verbose_name = 'Agent 网关 — AI 统一入口'

    def ready(self):
        """
        Django 启动时自动注册 MCP 工具到编排服务底座

        在子线程中执行，避免阻塞 Django 启动流程。
        编排服务可能还未就绪，通过重试机制兜底。
        """
        # 避免 manage.py migrate/makemigrations 等命令也触发注册
        import os
        import sys
        if os.environ.get('RUN_MAIN') == 'true' or 'runserver' in sys.argv:
            try:
                from .tool_registration import register_tools_on_startup
                register_tools_on_startup()
                logger.info("[AgentGateway] 已触发启动时工具注册（后台线程）")
            except Exception as e:
                logger.warning(f"[AgentGateway] 启动注册触发失败（非致命）: {e}")
