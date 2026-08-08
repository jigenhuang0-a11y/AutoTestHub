from django.apps import AppConfig


class ExecutionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'execution'

    def ready(self):
        # 启动定时任务调度器（仅主进程）
        import os
        if os.environ.get('RUN_MAIN') or not os.environ.get('DJANGO_AUTORELOAD'):
            from execution.scheduler import start_scheduler
            start_scheduler()
