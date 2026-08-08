# -*- coding: utf-8 -*-
import os, sys, django, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from django.contrib.auth import get_user_model
from ai_evaluator.models import EvalTask
from ai_evaluator.engine import AIEvaluatorEngine
import threading, traceback

User = get_user_model()
admin = User.objects.filter(username='admin').first()

tasks = EvalTask.objects.filter(created_by=admin, status='pending').order_by('-id')[:8]
print(f"🚀 准备执行 {len(tasks)} 个测评任务...\n")

for task in tasks:
    # 重置状态
    task.results.all().delete()
    if hasattr(task, 'report'):
        task.report.delete()
    task.correct_count = 0
    task.incorrect_count = 0
    task.partial_count = 0
    task.error_count = 0
    task.accuracy = 0.0
    task.avg_response_time = 0.0
    task.overall_score = 0.0
    task.security_issues_found = 0
    task.status = 'running'
    task.save()

    def _run(t=task):
        try:
            engine = AIEvaluatorEngine(t)
            engine.run_evaluation()
        except Exception as e:
            print(f"  ❌ 任务 #{t.id} 执行失败: {e}")
            traceback.print_exc()
            try:
                t.status = 'failed'
                t.save()
            except:
                pass

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    print(f"  ✅ 任务 #{task.id} ({task.name}) 已启动")
    time.sleep(3)

print("\n🎉 全部测评任务已启动执行，刷新页面查看结果")
