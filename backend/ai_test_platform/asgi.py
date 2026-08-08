"""
ASGI config for ai_test_platform project.

ASGI 模式启动（推荐用于 SSE 流式场景）:
    daphne -b 0.0.0.0 -p 8000 ai_test_platform.asgi:application

WSGI fallback:
    python manage.py runserver  (自动使用同步模式)
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')

# Django ASGI 应用（HTTP + SSE + WebSocket 均经由此入口）
application = get_asgi_application()
