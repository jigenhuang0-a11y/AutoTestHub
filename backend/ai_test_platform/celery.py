"""
Celery 配置 — 异步任务队列

启动 Worker:
    celery -A ai_test_platform worker -l info -P gevent

Beat (定时任务):
    celery -A ai_test_platform beat -l info
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')

app = Celery('ai_test_platform')

# 从 Django settings 加载配置（CELERY_ 前缀）
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现所有 app 下的 tasks.py
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
