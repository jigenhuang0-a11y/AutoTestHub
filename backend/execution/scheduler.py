"""
定时任务调度器 - 后台线程每分钟检查并执行已到时间的定时任务
在 apps.py 中启动
"""

import time
import threading
import logging
from django.utils import timezone
from django.db import connection

logger = logging.getLogger(__name__)

_scheduler_thread = None
_stop_event = threading.Event()


def _run_scheduled_tasks():
    """检查并执行所有已到达计划执行时间的 pending 定时任务"""
    from execution.models import TestExecution
    from execution.engine import TestExecutionEngine

    try:
        now = timezone.now()
        # 查找: status=pending + trigger_type=scheduled + scheduled_at <= now
        tasks = TestExecution.objects.filter(
            status='pending',
            trigger_type='scheduled',
            scheduled_at__lte=now,
        )

        for execution in tasks:
            logger.info(f'[Scheduler] 开始执行定时任务 #{execution.id}: {execution.name}')

            # 自动解锁：如果任务被锁定，到点自动解锁并执行
            if execution.locked:
                logger.warning(f'[Scheduler] 定时任务 #{execution.id} 已锁定，到点自动解锁')
                execution.locked = False
                execution.save(update_fields=['locked'])

            execution.status = 'running'
            execution.started_at = now
            execution.save(update_fields=['status', 'started_at'])

            try:
                # 获取套件的全局变量
                global_vars = {}
                if execution.test_suite and execution.test_suite.suite_vars:
                    suite_vars = execution.test_suite.suite_vars
                    if 'global_vars' in suite_vars:
                        for var in suite_vars['global_vars']:
                            if var.get('name') and var.get('value'):
                                global_vars[var['name']] = var['value']

                engine = TestExecutionEngine(execution.id, global_variables=global_vars)
                result = engine.execute()

                # 更新套件执行次数
                if execution.test_suite:
                    suite = execution.test_suite
                    suite.execution_count = (suite.execution_count or 0) + 1
                    suite.save(update_fields=['execution_count'])

                logger.info(f'[Scheduler] 定时任务 #{execution.id} 完成: {result.status} '
                           f'(通过={result.passed_count}, 失败={result.failed_count})')
            except Exception as e:
                execution.status = 'failed'
                execution.execution_log = f'[Scheduler ERROR] {str(e)}'
                execution.save()
                logger.error(f'[Scheduler] 定时任务 #{execution.id} 执行失败: {e}')

        # 关闭可能残留的数据库连接（线程安全）
        connection.close_if_unusable_or_obsolete()

    except Exception as e:
        logger.error(f'[Scheduler] 检查定时任务时出错: {e}')


def _scheduler_loop():
    """调度器主循环：每 60 秒检查一次"""
    logger.info('[Scheduler] 定时任务调度器已启动')
    while not _stop_event.is_set():
        _stop_event.wait(60)  # 每60秒检查一次
        if _stop_event.is_set():
            break
        _run_scheduled_tasks()
    logger.info('[Scheduler] 定时任务调度器已停止')


def start_scheduler():
    """启动调度器（Django apps ready 时调用）"""
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name='TaskScheduler')
    _scheduler_thread.start()


def stop_scheduler():
    """停止调度器（Django shutdown 时调用）"""
    _stop_event.set()
