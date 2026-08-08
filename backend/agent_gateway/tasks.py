"""
Agent 异步任务 — 通过 Celery 后台提交至底座 AI 编排服务

架构原则（规范5）：
- Celery 任务不再直接实例化 Agent 做调度决策
- 所有任务统一通过 HTTP 转发至底座的 /api/v1/workflow/invoke/
- Django Celery 仅负责：任务记录、状态追踪、失败重试
"""
import logging
import json
import requests
from celery import shared_task
from django.contrib.auth import get_user_model
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()

# 底座地址
AI_ORCHESTRATION_SERVICE_URL = getattr(settings, 'AI_ORCHESTRATION_SERVICE_URL', 'http://localhost:8001')
ORCHESTRATOR_TIMEOUT = getattr(settings, 'AI_ORCHESTRATION_REQUEST_TIMEOUT', (10, 300))


def _submit_to_orchestrator(user_request: str, user_id: int, team_id: str = "default",
                            template_id: str = None, auth_token: str = None) -> dict:
    """提交任务至底座 workflow invoke 端点，返回底座响应"""
    import urllib.parse
    url = urllib.parse.urljoin(AI_ORCHESTRATION_SERVICE_URL, '/api/v1/workflow/invoke/')
    resp = requests.post(
        url,
        json={
            'user_request': user_request,
            'user_id': user_id,
            'team_id': team_id,
            'template_id': template_id,
            'auth_token': auth_token,
        },
        timeout=ORCHESTRATOR_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def generate_testcases_task(self, user_id: int, requirement: str, strategy: str = "standard",
                             case_count: int = 10):
    """
    异步生成测试用例 → 转发至底座 workflow

    Args:
        user_id: 用户 ID
        requirement: 需求描述
        strategy: 生成策略 (standard/api_only/business/quick)
        case_count: 用例数量
    """
    from agent_gateway.models import AgentTask

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"[Celery] 用户不存在: {user_id}")
        return {"error": "用户不存在"}

    task = AgentTask.objects.create(
        task_type='testcase_generation',
        user_request=requirement,
        status='running',
        user=user,
    )

    # 构造底座工作流请求（user_request 包含结构化信息供 Plan 节点解析）
    workflow_request = json.dumps({
        "action": "generate_testcases",
        "requirement": requirement,
        "strategy": strategy,
        "case_count": case_count,
    }, ensure_ascii=False)

    try:
        result = _submit_to_orchestrator(
            user_request=workflow_request,
            user_id=user_id,
            team_id=str(user_id),
        )
        task.status = 'completed'
        task.result = result.get('results', {})
        task.steps_count = len(result.get('plan', []))
        task.save()
        return {"success": True, "task_id": task.id}

    except Exception as e:
        logger.exception(f"[Celery] 用例生成失败: {e}")
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def generate_data_task(
    self,
    user_id: int,
    business_domain: str = "",
    strategy: str = "smart",
    record_count: int = 10,
    fields: list = None,
    dataset_name: str = "",
    bind_testcase_ids: list = None,
):
    """
    异步生成测试数据 → 转发至底座 workflow

    Args:
        user_id: 用户 ID
        business_domain: 业务领域 (order/user/logistics/after_sales)
        strategy: 生成策略 (smart/boundary/template)
        record_count: 记录数
        fields: 自定义字段定义
        dataset_name: 数据集名称
        bind_testcase_ids: 绑定的用例 ID 列表
    """
    from agent_gateway.models import AgentTask

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"[Celery] 用户不存在: {user_id}")
        return {"error": "用户不存在"}

    task = AgentTask.objects.create(
        task_type='data_generation',
        user_request=f"生成 {business_domain or '自定义'} 数据",
        status='running',
        user=user,
    )

    workflow_request = json.dumps({
        "action": "generate_data",
        "business_domain": business_domain,
        "strategy": strategy,
        "record_count": record_count,
        "fields": fields or [],
        "dataset_name": dataset_name,
        "bind_testcase_ids": bind_testcase_ids or [],
    }, ensure_ascii=False)

    try:
        result = _submit_to_orchestrator(
            user_request=workflow_request,
            user_id=user_id,
            team_id=str(user_id),
        )
        task.status = 'completed'
        task.result = result.get('results', {})
        task.steps_count = len(result.get('plan', []))
        task.save()
        return {"success": True, "task_id": task.id}

    except Exception as e:
        logger.exception(f"[Celery] 数据生成失败: {e}")
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def execute_tests_task(
    self,
    user_id: int,
    suite_id: int = None,
    test_case_ids: list = None,
    environment: str = "dev",
    max_retries: int = 2,
    global_variables: dict = None,
    analyze_failures: bool = True,
):
    """
    异步执行测试套件 → 转发至底座 workflow

    Args:
        user_id: 用户 ID
        suite_id: 套件 ID
        test_case_ids: 用例 ID 列表
        environment: 环境 (dev/test/prod)
        max_retries: 最大重试次数
        global_variables: 全局变量
        analyze_failures: 是否 AI 分析失败原因
    """
    from agent_gateway.models import AgentTask

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"[Celery] 用户不存在: {user_id}")
        return {"error": "用户不存在"}

    task = AgentTask.objects.create(
        task_type='execution',
        user_request=f"执行测试: suite={suite_id}",
        status='running',
        user=user,
    )

    workflow_request = json.dumps({
        "action": "execute_tests",
        "suite_id": suite_id,
        "test_case_ids": test_case_ids or [],
        "environment": environment,
        "max_retries": max_retries,
        "global_variables": global_variables or {},
        "analyze_failures": analyze_failures,
    }, ensure_ascii=False)

    try:
        result = _submit_to_orchestrator(
            user_request=workflow_request,
            user_id=user_id,
            team_id=str(user_id),
        )
        task.status = 'completed'
        task.result = result.get('results', {})
        task.steps_count = len(result.get('plan', []))
        task.save()
        return {"success": True, "task_id": task.id, "execution_id": result.get('task_id')}

    except Exception as e:
        logger.exception(f"[Celery] 测试执行失败: {e}")
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def evaluate_execution_task(
    self,
    user_id: int,
    execution_id: int,
    suite_id: int = None,
    trend_days: int = 7,
    generate_html: bool = True,
):
    """
    异步评估执行结果 → 转发至底座 workflow

    Args:
        user_id: 用户 ID
        execution_id: 执行记录 ID
        suite_id: 关联套件
        trend_days: 趋势分析天数
        generate_html: 是否生成 HTML 报告
    """
    from agent_gateway.models import AgentTask

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"[Celery] 用户不存在: {user_id}")
        return {"error": "用户不存在"}

    task = AgentTask.objects.create(
        task_type='evaluation',
        user_request=f"评估执行 #{execution_id}",
        status='running',
        user=user,
    )

    workflow_request = json.dumps({
        "action": "evaluate",
        "execution_id": execution_id,
        "suite_id": suite_id,
        "trend_days": trend_days,
        "generate_html": generate_html,
    }, ensure_ascii=False)

    try:
        result = _submit_to_orchestrator(
            user_request=workflow_request,
            user_id=user_id,
            team_id=str(user_id),
        )
        task.status = 'completed'
        task.result = result.get('results', {})
        task.steps_count = 1
        task.save()
        return {"success": True, "task_id": task.id, "report_id": result.get('task_id')}

    except Exception as e:
        logger.exception(f"[Celery] 评估失败: {e}")
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        raise self.retry(exc=e)
