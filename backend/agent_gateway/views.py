"""
Agent Gateway 视图 — 统一 AI 入口 API

架构原则（规范5）：
- 所有 LLM 调用统一转发至底座（ai-orchestration-service）的 /api/v1/llm/ 端点
- 所有智能体工作流统一转发至底座的 /api/v1/workflow/ 端点
- Django 仅负责：任务记录、用户认证、Prompt 配置管理、业务工具执行
- 严禁在 Django 内直接调用 LLMRouter 或实例化 Agent 做调度决策
"""
import logging
import os
import uuid
import json
import requests
import httpx
import urllib.parse
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import StreamingHttpResponse

from .models import AgentTask, AgentPromptConfig
from .serializers import AgentTaskSerializer, AgentPromptConfigSerializer
from .circuit_breaker import get_orchestration_circuit_breaker

# 业务工具 Agent（非调度层，仅作 MCP 工具实现）
# 这些 Agent 是 Django 工具层的具体执行者，
# 底座通过 MCP ToolGateway 调用它们，而非 Django 直接做调度决策
from core.agents.testcase_gen_agent import TestCaseGeneratorAgent
from core.agents.data_factory_agent import DataFactoryAgent
from core.agents.execution_agent import ExecutionEngineAgent
from core.agents.evaluator_agent import EvaluatorAgent

# LLMRouter（仅作为工具 Agent 的 LLM 依赖注入，不做调度路由）
# 工具 Agent 需要通过 LLM 完成 AI 生成/评估等工具功能，
# 工具层的 LLM 调用不属于调度层决策
from core.models.router import get_llm_router

logger = logging.getLogger(__name__)

# 底座 AI 编排服务地址
AI_ORCHESTRATION_SERVICE_URL = getattr(settings, 'AI_ORCHESTRATION_SERVICE_URL', 'http://localhost:8001')

# 熔断器配置
AI_ORCHESTRATION_CB_FAILURE_THRESHOLD = getattr(settings, 'AI_ORCHESTRATION_CB_FAILURE_THRESHOLD', 5)
AI_ORCHESTRATION_CB_RECOVERY_TIMEOUT = getattr(settings, 'AI_ORCHESTRATION_CB_RECOVERY_TIMEOUT', 60)
AI_ORCHESTRATION_CB_HALF_OPEN_MAX_CALLS = getattr(settings, 'AI_ORCHESTRATION_CB_HALF_OPEN_MAX_CALLS', 1)
AI_ORCHESTRATION_REQUEST_TIMEOUT = getattr(settings, 'AI_ORCHESTRATION_REQUEST_TIMEOUT', (10, 300))

_orchestration_cb = get_orchestration_circuit_breaker(
    failure_threshold=AI_ORCHESTRATION_CB_FAILURE_THRESHOLD,
    recovery_timeout=AI_ORCHESTRATION_CB_RECOVERY_TIMEOUT,
    half_open_max_calls=AI_ORCHESTRATION_CB_HALF_OPEN_MAX_CALLS,
)


def _check_orchestrator_available():
    """检查底座是否可达，不可达直接拒绝请求（不再有本地回退）"""
    if not AI_ORCHESTRATION_SERVICE_URL:
        raise OrchestratorUnavailable("编排服务未配置，请设置 AI_ORCHESTRATION_SERVICE_URL")
    cb = _orchestration_cb
    if not cb.can_call():
        raise OrchestratorUnavailable(f"编排服务熔断器处于 {cb.state_label} 状态，暂时不可用")


def _build_forward_headers(request) -> dict:
    """
    构建转发至底座的请求头，包含 OTel trace context + JWT 鉴权。

    - 从当前请求中提取 Authorization: Bearer <jwt>
    - 附加 SERVICE_TOKEN 作为服务间 fallback
    - 注入 OTel traceparent
    """
    from core.telemetry import inject_context
    headers = inject_context() or {}

    # 透传用户 JWT（底座 AuthMiddleware 将验证此 Token）
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header:
        headers['Authorization'] = auth_header

    # 附加服务间通行令牌（供底座 SERVICE_TOKEN 通道 fallback）
    service_token = getattr(settings, 'SERVICE_TOKEN', None) or os.getenv('SERVICE_TOKEN', '')
    if service_token:
        headers['X-Service-Token'] = service_token

    return headers


class OrchestratorUnavailable(Exception):
    """底座不可用异常"""
    pass


class AgentTaskViewSet(viewsets.ModelViewSet):
    serializer_class = AgentTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AgentTask.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def invoke(self, request):
        """
        通用 Agent 调用入口（全部转发至底座 LLM 端点）

        POST /api/agent/tasks/invoke/
        {
            "task_type": "code_generation",   // 任务类型（决定路由到哪个模型）
            "prompt": "写一个排序函数",         // 用户输入
            "model": "deepseek-chat",         // 可选：指定模型
            "stream": false                   // 是否流式返回
        }
        """
        task_type = request.data.get('task_type', 'fast_chat')
        prompt = request.data.get('prompt', '')
        model = request.data.get('model')
        stream = request.data.get('stream', False)

        if not prompt:
            return Response({'error': 'prompt 不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 底座可用性检查（不可用直接拒绝，不本地回退）
        try:
            _check_orchestrator_available()
        except OrchestratorUnavailable as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 创建任务记录
        task = AgentTask.objects.create(
            task_type=task_type,
            user_request=prompt,
            status='running',
            user=request.user,
        )

        if stream:
            return self._proxy_llm_stream(request, task, task_type, prompt, model)

        return self._proxy_llm_chat(request, task, task_type, prompt, model)

    def _proxy_llm_chat(self, request, task, task_type, prompt, model):
        """将 LLM 调用转发至底座 /api/v1/llm/chat/（异步非阻塞）"""
        url = urllib.parse.urljoin(AI_ORCHESTRATION_SERVICE_URL, '/api/v1/llm/chat')
        try:
            from core.telemetry import inject_context, get_tracer
            tracer = get_tracer()
            with tracer.start_as_current_span("agent_gateway.llm_chat") as span:
                span.set_attribute("task_type", task_type)
                span.set_attribute("task_id", str(task.id))
                resp = requests.post(
                    url,
                    json={
                        'messages': [{'role': 'user', 'content': prompt}],
                        'task_type': task_type,
                        'model': model,
                    },
                    headers=_build_forward_headers(request),
                    timeout=AI_ORCHESTRATION_REQUEST_TIMEOUT,
                )
            resp.raise_for_status()
            data = resp.json()
            _orchestration_cb.record_success()

            task.status = 'completed'
            task.result = {'answer': data.get('answer', ''), 'model_used': data.get('model_used', 'auto')}
            task.save()

            return Response({
                'task_id': task.id,
                'status': 'completed',
                'answer': data.get('answer', ''),
                'model_used': data.get('model_used', 'auto'),
            })

        except requests.RequestException as e:
            _orchestration_cb.record_failure()
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
            logger.exception(f"[AgentGateway] 底座 LLM 调用失败: {e}")
            return Response({
                'task_id': task.id,
                'status': 'failed',
                'error': f'底座 LLM 调用失败: {str(e)}',
            }, status=status.HTTP_502_BAD_GATEWAY)

    def _proxy_llm_stream(self, request, task, task_type, prompt, model):
        """将流式 LLM 调用转发至底座 /api/v1/llm/chat/stream/，异步非阻塞透传 SSE。

        - ASGI 模式（daphne）：原生 async/await，单 worker 高并发 SSE，无线程阻塞。
        - WSGI 模式（runserver）：Django 内部 sync_to_async 驱动，兼容现有开发流程。
        """
        url = urllib.parse.urljoin(AI_ORCHESTRATION_SERVICE_URL, '/api/v1/llm/chat/stream')

        from core.telemetry import inject_context, get_tracer
        tracer = get_tracer()
        stream_headers = _build_forward_headers(request)
        # 手动管理 Span（不能用 with，generator 是延迟消费的）
        span = tracer.start_span("agent_gateway.llm_stream")

        async def _async_generate():
            full_answer = ''
            remote_success = False
            try:
                async with httpx.AsyncClient(timeout=AI_ORCHESTRATION_REQUEST_TIMEOUT) as client:
                    async with client.stream(
                        'POST', url,
                        json={
                            'messages': [{'role': 'user', 'content': prompt}],
                            'task_type': task_type,
                            'model': model,
                        },
                        headers=stream_headers,
                    ) as resp:
                        if resp.status_code >= 400:
                            body = await resp.aread()
                            logger.error(f"[Gateway] 底座 SSE 错误 {resp.status_code}: {body[:300]}")
                            yield f"data: {json.dumps({'error': f'底座返回 {resp.status_code}'}, ensure_ascii=False)}\n\n"
                            return

                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            yield line + '\n\n'
                            if line.startswith('data:'):
                                try:
                                    event = json.loads(line[5:].strip())
                                    if 'chunk' in event:
                                        full_answer += event['chunk']
                                except json.JSONDecodeError:
                                    pass

                remote_success = True
                from asgiref.sync import sync_to_async
                task.status = 'completed'
                task.result = {'answer': full_answer, 'model_used': str(model or 'auto')}
                await sync_to_async(task.save)()

            except Exception as e:
                logger.exception(f"[AgentGateway] 底座 LLM 流式调用失败: {e}")
                from asgiref.sync import sync_to_async
                task.status = 'failed'
                task.error_message = str(e)
                await sync_to_async(task.save)()
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

            finally:
                span.set_attribute("remote_success", remote_success)
                span.end()
                if remote_success:
                    _orchestration_cb.record_success()
                else:
                    _orchestration_cb.record_failure()

        response = StreamingHttpResponse(
            _async_generate(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            }
        )
        response['X-Task-ID'] = str(task.id)
        return response

    @action(detail=False, methods=['post'])
    def workflow_stream(self, request):
        """
        SSE 流式工作流执行 — 实时推送每个步骤的进度

        全部转发到独立 AI 编排服务（唯一大脑），不再有本地回退路径。

        POST /api/agent/tasks/workflow_stream/
        {
            "user_request": "帮我测试订单系统的创建订单接口",
            "knowledge_base_id": null,
        }
        """
        user_request = request.data.get('user_request', '')
        knowledge_base_id = request.data.get('knowledge_base_id')

        if not user_request:
            return Response({'error': 'user_request 不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        if not AI_ORCHESTRATION_SERVICE_URL:
            return Response(
                {'error': '编排服务未配置，请设置 AI_ORCHESTRATION_SERVICE_URL'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 创建任务记录
        task = AgentTask.objects.create(
            task_type='workflow',
            user_request=user_request,
            status='running',
            user=request.user,
        )

        # 熔断器检查
        cb = _orchestration_cb
        if not cb.can_call():
            return Response(
                {'error': f'编排服务熔断器处于 {cb.state_label} 状态，暂时不可用'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            return self._stream_from_orchestration_service(
                request, task, user_request, knowledge_base_id, cb=cb
            )
        except Exception as e:
            cb.record_failure()
            logger.exception(f"[AgentGateway] 编排服务调用失败: {e}")
            return Response(
                {'error': f'编排服务调用失败: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    def _stream_from_orchestration_service(self, request, task, user_request, knowledge_base_id, cb=None):
        """将工作流请求转发到独立编排服务，异步非阻塞透传 SSE 流。

        - ASGI 模式（daphne）：原生 async/await 高并发。
        - WSGI 模式（runserver）：Django 内部 sync_to_async 驱动，兼容开发流程。
        """
        import urllib.parse
        url = urllib.parse.urljoin(AI_ORCHESTRATION_SERVICE_URL, '/api/v1/workflow/stream')
        
        # 提取前端传入的 Authorization Token
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        payload = {
            'user_request': user_request,
            'user_id': request.user.id,
            'auth_token': auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else auth_header,
        }

        session_id = str(uuid.uuid4())[:12]

        from core.telemetry import inject_context, get_tracer
        tracer = get_tracer()
        wf_headers = _build_forward_headers(request)
        # 手动管理 Span（generator 延迟消费，不能使用 with）
        wf_span = tracer.start_span("agent_gateway.workflow_stream")

        async def _async_generate():
            workflow_result = ''
            remote_success = False
            try:
                async with httpx.AsyncClient(timeout=AI_ORCHESTRATION_REQUEST_TIMEOUT) as client:
                    async with client.stream(
                        'POST', url, json=payload, headers=wf_headers
                    ) as resp:
                        if resp.status_code >= 400:
                            body = await resp.aread()
                            logger.error(f"[Gateway] 工作流 SSE 错误 {resp.status_code}: {body[:300]}")
                            yield f"data: {json.dumps({'event': 'error', 'data': {'message': f'底座返回 {resp.status_code}'}}, ensure_ascii=False)}\n\n"
                            return

                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            yield line + '\n\n'
                            if line.startswith('data:'):
                                try:
                                    event = json.loads(line[5:].strip())
                                    if event.get('event') == 'workflow_complete':
                                        workflow_result = event.get('data', {}).get('summary', '')
                                except json.JSONDecodeError:
                                    pass

                remote_success = True
                from asgiref.sync import sync_to_async
                task.status = 'completed'
                task.steps_count = 1
                await sync_to_async(task.save)()

            except Exception as e:
                logger.exception(f"编排服务流式执行失败: {e}")
                from asgiref.sync import sync_to_async
                task.status = 'failed'
                task.error_message = str(e)
                await sync_to_async(task.save)()
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}}, ensure_ascii=False)}\n\n"

            finally:
                wf_span.set_attribute("remote_success", remote_success)
                wf_span.end()
                if cb is not None:
                    if remote_success:
                        cb.record_success()
                    else:
                        cb.record_failure()

                # 保存到 ChatMessage（async ORM 必须在 generator finally 中）
                if knowledge_base_id:
                    try:
                        from knowledge_base.models import ChatMessage, KnowledgeBase
                        from asgiref.sync import sync_to_async
                        kb = await sync_to_async(KnowledgeBase.objects.get)(id=knowledge_base_id)
                        await sync_to_async(ChatMessage.objects.create)(
                            knowledge_base=kb,
                            session_id=session_id,
                            mode='workflow',
                            question=user_request,
                            answer=workflow_result or '多Agent工作流执行完成',
                            created_by=request.user
                        )
                    except Exception as save_err:
                        logger.warning(f"保存工作流历史记录失败: {save_err}")

        response = StreamingHttpResponse(
            _async_generate(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            }
        )
        response['X-Task-ID'] = str(task.id)
        return response

    @action(detail=False, methods=['get'], url_path='progress/(?P<task_id>\\d+)')
    def workflow_progress(self, request, task_id=None):
        """
        轮询工作流进度 — 代理到编排服务的 Checkpoint API

        GET /api/agent/tasks/progress/123/
        """
        import urllib.parse
        if not AI_ORCHESTRATION_SERVICE_URL:
            return Response({'error': '编排服务未配置'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            url = urllib.parse.urljoin(
                AI_ORCHESTRATION_SERVICE_URL,
                f'/api/v1/checkpoints/{task_id}/'
            )
            resp = requests.get(url, timeout=(3, 10))
            resp.raise_for_status()
            return Response(resp.json())
        except requests.RequestException as e:
            logger.warning(f"[AgentGateway] 查询编排服务进度失败: {e}")
            return Response({'exists': False, 'message': f'查询进度失败: {str(e)}'})

    @action(detail=False, methods=['post'])
    def workflow(self, request):
        """
        LangGraph 工作流调用入口 — 转发到编排服务

        POST /api/agent/tasks/workflow/
        {
            "user_request": "帮我测试订单系统的创建订单接口"
        }
        """
        import urllib.parse
        user_request = request.data.get('user_request', '')

        if not user_request:
            return Response({'error': 'user_request 不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        if not AI_ORCHESTRATION_SERVICE_URL:
            return Response(
                {'error': '编排服务未配置'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 创建任务记录
        task = AgentTask.objects.create(
            task_type='workflow',
            user_request=user_request,
            status='running',
            user=request.user,
        )

        try:
            url = urllib.parse.urljoin(
                AI_ORCHESTRATION_SERVICE_URL, '/api/v1/workflow/invoke/'
            )
            resp = requests.post(
                url,
                json={
                    'user_request': user_request,
                    'user_id': request.user.id,
                },
                timeout=AI_ORCHESTRATION_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            task.status = 'completed'
            task.result = data.get('result', {})
            task.steps_count = data.get('steps_count', 0)
            task.save()

            return Response({
                'task_id': task.id,
                'status': 'completed',
                **data,
            })

        except requests.RequestException as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
            logger.exception(f"[AgentGateway] 编排服务工作流调用失败: {e}")
            return Response({
                'task_id': task.id,
                'status': 'failed',
                'error': str(e),
            }, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=False, methods=['get'])
    def models(self, request):
        """列出所有可用模型（代理底座 LLMRouter）"""
        try:
            url = urllib.parse.urljoin(AI_ORCHESTRATION_SERVICE_URL, '/api/v1/llm/models')
            resp = requests.get(url, timeout=(3, 10))
            resp.raise_for_status()
            return Response(resp.json())
        except requests.RequestException:
            # 底座不可用时，尝试本地读取模型配置（纯信息展示，不涉及调度）
            try:
                from core.config import get_available_providers, MODEL_REGISTRY
                available = get_available_providers()
                models_list = sorted(
                    [{"name": n, "provider": c.provider, "capabilities": c.capabilities, "priority": c.priority}
                     for n, c in MODEL_REGISTRY.items() if c.provider in available],
                    key=lambda m: m["priority"], reverse=True
                )
                return Response({"models": models_list, "_source": "local_fallback"})
            except Exception:
                return Response({"models": [], "error": "底座和本地模型列表均不可用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def health(self, request):
        """健康检查"""
        router = get_llm_router()
        from core.config import get_available_providers

        orchestrator_reachable = False
        if AI_ORCHESTRATION_SERVICE_URL:
            try:
                import urllib.parse
                ping_url = urllib.parse.urljoin(
                    AI_ORCHESTRATION_SERVICE_URL, '/api/v1/health/'
                )
                requests.get(ping_url, timeout=(3, 5))
                orchestrator_reachable = True
            except Exception:
                orchestrator_reachable = False

        return Response({
            'status': 'ok',
            'available_providers': sorted(get_available_providers()),
            'total_models': len(router.get_available_models()),
            'ai_orchestration': {
                'url': AI_ORCHESTRATION_SERVICE_URL,
                'reachable': orchestrator_reachable,
                'circuit_breaker': {
                    'state': _orchestration_cb.state_label,
                    'failure_threshold': _orchestration_cb.failure_threshold,
                    'recovery_timeout': _orchestration_cb.recovery_timeout,
                },
            },
        })


    @action(detail=False, methods=['post'])
    def generate_testcases(self, request):
        """
        用例生成工具端点（工具层，非调度层）

        架构定位：此端点属于 Django 工具层，直接调用 TestCaseGeneratorAgent。
        底座通过 MCP ToolGateway 发现并调用此工具，编排逻辑在底座的
        Plan → Orchestrate(dispatch tool) → Verify 流程中。

        POST /api/agent/tasks/generate_testcases/
        {
            "requirement": "用户登录功能",
            "strategy": "standard",        // standard/api_only/business/quick
            "case_count": 10,              // 生成用例数量
            "save_to_db": true,            // 是否保存到数据库
            "knowledge_doc_ids": [],       // 可选：指定知识库文档
            "extra_context": ""            // 可选：额外上下文
        }
        """
        requirement = request.data.get('requirement', '')
        strategy = request.data.get('strategy', 'standard')
        case_count = int(request.data.get('case_count', 10))
        save_to_db = request.data.get('save_to_db', True)

        if not requirement:
            return Response({'error': 'requirement 不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 创建任务记录
        task = AgentTask.objects.create(
            task_type='testcase_generation',
            user_request=requirement,
            status='running',
            user=request.user,
        )

        try:
            # 创建 Agent 并执行
            agent = TestCaseGeneratorAgent(
                user_id=request.user.id,
                router=get_llm_router(),
            )
            result = agent.run(
                prompt=requirement,
                context={
                    'strategy': strategy,
                    'case_count': case_count,
                    'knowledge_context': request.data.get('knowledge_context', ''),
                    'extra_context': request.data.get('extra_context', ''),
                },
            )

            if result.get('status') == 'success':
                cases = result.get('data', [])

                # 保存到数据库
                if save_to_db and cases:
                    from core.tools.testcase_storage import TestCaseStorageTool
                    storage = TestCaseStorageTool(user_id=request.user.id)
                    save_results = storage.save_cases(
                        cases=cases,
                        batch_name=f"AI生成-{strategy}",
                    )
                    saved_count = sum(1 for r in save_results if r.success)
                    case_ids = [r.case_id for r in save_results if r.success and r.case_id]
                else:
                    saved_count = 0
                    case_ids = []

                task.status = 'completed'
                task.result = {
                    'cases': cases,
                    'stats': result.get('stats', {}),
                    'saved_count': saved_count,
                    'case_ids': case_ids,
                }
                task.steps_count = len(cases)
                task.save()

                return Response({
                    'task_id': task.id,
                    'status': 'completed',
                    'cases': cases,
                    'case_count': len(cases),
                    'saved_count': saved_count,
                    'case_ids': case_ids,
                    'stats': result.get('stats', {}),
                })
            else:
                task.status = 'failed'
                task.error_message = result.get('error', '未知错误')
                task.save()
                return Response({
                    'task_id': task.id,
                    'status': 'failed',
                    'error': result.get('error', '未知错误'),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
            logger.exception(f"用例生成失败: {e}")
            return Response({
                'task_id': task.id,
                'status': 'failed',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def generate_data(self, request):
        """
        数据工厂工具端点（工具层，非调度层）

        架构定位：Django 工具层直接调用 DataFactoryAgent。
        底座通过 MCP ToolGateway 发现并调用。

        POST /api/agent/tasks/generate_data/
        {
            "business_domain": "order",       // order/user/logistics/after_sales
            "fields": [                        // 可选：自定义字段定义
                {"name": "order_id", "type": "string", "description": "订单号"}
            ],
            "strategy": "smart",               // smart/boundary/template
            "record_count": 20,                // 生成数量
            "dataset_name": "订单测试数据集",    // 可选
            "bind_testcase_ids": [1, 2, 3],    // 可选：自动绑定的用例ID
            "extra_context": ""                // 可选：额外约束
        }
        """
        business_domain = request.data.get('business_domain', '')
        fields = request.data.get('fields', None)
        strategy = request.data.get('strategy', 'smart')
        record_count = int(request.data.get('record_count', 10))
        dataset_name = request.data.get('dataset_name', '')
        bind_testcase_ids = request.data.get('bind_testcase_ids', [])
        extra_context = request.data.get('extra_context', '')

        if not business_domain and not fields:
            return Response(
                {'error': 'business_domain 或 fields 至少需要一个'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 创建任务记录
        task = AgentTask.objects.create(
            task_type='data_generation',
            user_request=f"生成 {business_domain or '自定义'} 业务数据",
            status='running',
            user=request.user,
        )

        try:
            agent = DataFactoryAgent(
                user_id=request.user.id,
                router=get_llm_router(),
            )
            result = agent.run(
                prompt=f"生成 {business_domain or '自定义'} 业务测试数据，策略: {strategy}",
                context={
                    'fields': fields,
                    'strategy': strategy,
                    'business_domain': business_domain,
                    'record_count': record_count,
                    'dataset_name': dataset_name,
                    'bind_testcase_ids': bind_testcase_ids,
                    'extra_context': extra_context,
                },
            )

            if result.get('status') == 'success':
                stats = result.get('stats', {})
                binding_results = result.get('binding_results', [])

                task.status = 'completed'
                task.result = {
                    'dataset_id': stats.get('dataset_id'),
                    'dataset_name': stats.get('dataset_name'),
                    'stats': stats,
                    'sample_records': result.get('data', [])[:5],
                    'binding_results': binding_results,
                }
                task.steps_count = stats.get('saved', 0)
                task.save()

                return Response({
                    'task_id': task.id,
                    'status': 'completed',
                    'dataset_id': stats.get('dataset_id'),
                    'dataset_name': stats.get('dataset_name'),
                    'record_count': stats.get('saved', 0),
                    'stats': stats,
                    'sample_records': result.get('data', [])[:5],
                    'binding_results': binding_results,
                })
            else:
                task.status = 'failed'
                task.error_message = result.get('error', '未知错误')
                task.save()
                return Response({
                    'task_id': task.id,
                    'status': 'failed',
                    'error': result.get('error', '未知错误'),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
            logger.exception(f"数据生成失败: {e}")
            return Response({
                'task_id': task.id,
                'status': 'failed',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def execute_tests(self, request):
        """
        执行引擎工具端点（工具层，非调度层）

        架构定位：Django 工具层直接调用 ExecutionEngineAgent。
        底座通过 MCP ToolGateway 发现并调用。

        POST /api/agent/tasks/execute_tests/
        {
            "suite_id": 1,                   // 套件 ID（与 test_case_ids 二选一或都传）
            "test_case_ids": [1, 2, 3],      // 用例 ID 列表
            "environment": "test",            // dev/test/prod
            "max_retries": 2,                 // 最大重试次数
            "global_variables": {             // 全局变量
                "base_url": "https://api.example.com",
                "token": "xxx"
            },
            "analyze_failures": true          // 是否 AI 分析失败原因
        }
        """
        suite_id = request.data.get('suite_id')
        test_case_ids = request.data.get('test_case_ids', [])
        environment = request.data.get('environment', 'dev')
        max_retries = int(request.data.get('max_retries', 2))
        global_variables = request.data.get('global_variables', {})
        analyze_failures = request.data.get('analyze_failures', True)

        if not suite_id and not test_case_ids:
            return Response(
                {'error': 'suite_id 或 test_case_ids 至少需要一个'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 创建任务记录
        task = AgentTask.objects.create(
            task_type='execution',
            user_request=f"执行测试: suite={suite_id}, cases={len(test_case_ids)}个",
            status='running',
            user=request.user,
        )

        try:
            agent = ExecutionEngineAgent(
                user_id=request.user.id,
                router=get_llm_router(),
            )

            result = agent.run(
                prompt=f"执行测试套件 {suite_id or '自定义用例集'}，环境: {environment}",
                context={
                    'suite_id': suite_id,
                    'test_case_ids': test_case_ids,
                    'environment': environment,
                    'max_retries': max_retries,
                    'global_variables': global_variables,
                    'analyze_failures': analyze_failures,
                },
            )

            if result.get('status') == 'success':
                data = result.get('data', {})
                stats = data.get('stats', {})
                summary = data.get('summary', {})
                report = data.get('report', {})

                task.status = 'completed'
                task.result = {
                    'execution_id': data.get('execution_id'),
                    'stats': stats,
                    'summary': summary,
                    'report': report,
                }
                task.steps_count = stats.get('total', 0)
                task.save()

                return Response({
                    'task_id': task.id,
                    'status': 'completed',
                    'execution_id': data.get('execution_id'),
                    'stats': stats,
                    'summary': summary,
                    'report': report,
                    'results_preview': data.get('results', [])[:10],
                })
            else:
                task.status = 'failed'
                task.error_message = result.get('error', '未知错误')
                task.save()
                return Response({
                    'task_id': task.id,
                    'status': 'failed',
                    'error': result.get('error', '未知错误'),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
            logger.exception(f"测试执行失败: {e}")
            return Response({
                'task_id': task.id,
                'status': 'failed',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def evaluate(self, request):
        """
        评估工具端点（工具层，非调度层）

        架构定位：Django 工具层直接调用 EvaluatorAgent。
        底座通过 MCP ToolGateway 发现并调用。

        POST /api/agent/tasks/evaluate/
        {
            "execution_id": 42,             // 必填：执行记录 ID
            "suite_id": 1,                  // 可选：关联套件（用于趋势分析）
            "trend_days": 7,                // 趋势分析天数（默认7）
            "generate_html": true           // 是否生成 HTML 报告
        }
        """
        execution_id = request.data.get('execution_id')
        suite_id = request.data.get('suite_id')
        trend_days = int(request.data.get('trend_days', 7))
        generate_html = request.data.get('generate_html', True)

        if not execution_id:
            return Response(
                {'error': 'execution_id 是必填参数'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 创建任务记录
        task = AgentTask.objects.create(
            task_type='evaluation',
            user_request=f"评估执行 #{execution_id}",
            status='running',
            user=request.user,
        )

        try:
            agent = EvaluatorAgent(
                user_id=request.user.id,
                router=get_llm_router(),
            )

            result = agent.run(
                prompt=f"评估执行记录 #{execution_id}",
                context={
                    'execution_id': execution_id,
                    'suite_id': suite_id,
                    'trend_days': trend_days,
                    'generate_html': generate_html,
                },
            )

            if result.get('status') == 'success':
                data = result.get('data', {})
                composite = data.get('composite_score', {})
                rule_scores = data.get('rule_scores', {})
                ai_eval = data.get('ai_evaluation', {})

                task.status = 'completed'
                task.result = {
                    'execution_id': execution_id,
                    'report_id': data.get('report_id'),
                    'composite_score': composite,
                    'rule_scores': {
                        'total': rule_scores.get('total_rule_score'),
                        'pass': rule_scores.get('pass_score'),
                        'stability': rule_scores.get('stability_score'),
                        'efficiency': rule_scores.get('efficiency_score'),
                    },
                    'ai_evaluation': ai_eval,
                    'history_trend': data.get('history_trend'),
                }
                task.steps_count = 1
                task.save()

                return Response({
                    'task_id': task.id,
                    'status': 'completed',
                    'execution_id': execution_id,
                    'report_id': data.get('report_id'),
                    'composite_score': composite,
                    'rule_scores': rule_scores,
                    'ai_evaluation': ai_eval,
                    'history_trend': data.get('history_trend'),
                })
            else:
                task.status = 'failed'
                task.error_message = result.get('error', '未知错误')
                task.save()
                return Response({
                    'task_id': task.id,
                    'status': 'failed',
                    'error': result.get('error', '未知错误'),
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
            logger.exception(f"评估失败: {e}")
            return Response({
                'task_id': task.id,
                'status': 'failed',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ============================================================
    # Prompt 配置管理 — 数据库驱动，无需重新部署
    # ============================================================

    @action(detail=False, methods=['get', 'put'], url_path='prompts')
    def manage_prompts(self, request):
        """
        Agent Prompt 配置管理 — 无需重新部署即可热更新
        
        GET  /api/agent/tasks/prompts/                     → 列出所有 prompt 配置
        GET  /api/agent/tasks/prompts/?agent=test_case_generator → 按 Agent 筛选
        PUT  /api/agent/tasks/prompts/                     → 批量更新/创建
        
        请求体示例（PUT）：
        {
            "prompts": [
                {
                    "agent_name": "test_case_generator",
                    "prompt_subtype": "default",
                    "system_prompt": "你是资深测试架构师...",
                    "is_active": true
                }
            ]
        }
        """
        if request.method == 'GET':
            agent_filter = request.query_params.get('agent', '')
            qs = AgentPromptConfig.objects.filter(is_active=True)
            if agent_filter:
                qs = qs.filter(agent_name=agent_filter)
            serializer = AgentPromptConfigSerializer(qs, many=True)
            return Response({'prompts': serializer.data, 'count': qs.count()})

        if request.method == 'PUT':
            prompts_data = request.data.get('prompts', [])
            if not prompts_data:
                return Response({'error': 'prompts 列表不能为空'}, status=400)

            updated = []
            for item in prompts_data:
                agent_name = item.get('agent_name')
                prompt_subtype = item.get('prompt_subtype', 'default')
                if not agent_name:
                    continue

                config, created = AgentPromptConfig.objects.update_or_create(
                    agent_name=agent_name,
                    prompt_subtype=prompt_subtype,
                    defaults={
                        'system_prompt': item.get('system_prompt', ''),
                        'user_prompt_template': item.get('user_prompt_template', ''),
                        'prompt_type': item.get('prompt_type', 'system'),
                        'description': item.get('description', ''),
                        'is_active': item.get('is_active', True),
                    }
                )
                # 版本号递增
                config.version = config.version + 1
                config.save(update_fields=['version', 'updated_at'])
                
                updated.append({
                    'agent_name': agent_name,
                    'prompt_subtype': prompt_subtype,
                    'version': config.version,
                    'action': 'created' if created else 'updated',
                })

            return Response({'status': 'ok', 'updated': updated, 'count': len(updated)})

    # ============================================================
    # 以下 _stream_response 已废弃替换为 _proxy_llm_stream（代理底座）
    # ============================================================


# ============================================================
# 审计代理 — 将前端的 /api/agent/audit/* 请求代理到 agent-harness
# ============================================================
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Agent Harness 底座地址
_AGENT_HARNESS_URL = getattr(settings, 'AI_ORCHESTRATION_SERVICE_URL', 'http://localhost:8100')


@csrf_exempt
def audit_proxy(request, subpath=''):
    """审计大屏代理 → agent-harness /api/v1/audit/<subpath>"""
    target_url = f"{_AGENT_HARNESS_URL}/api/v1/audit/{subpath}"
    if request.META.get('QUERY_STRING'):
        target_url += f"?{request.META['QUERY_STRING']}"

    logger.info(f"[AuditProxy] {request.method} {target_url}")

    try:
        resp = httpx.request(
            method=request.method,
            url=target_url,
            headers={
                k: v for k, v in request.headers.items()
                if k.lower() not in ('host', 'content-length')
            },
            content=request.body,
            timeout=10.0,
        )
        return JsonResponse(resp.json(), safe=False, status=resp.status_code)
    except httpx.ConnectError:
        # agent-harness 未启动时返回空数据，不报错
        return JsonResponse({
            "success": True,
            "data": {"events": [], "total": 0},
            "note": "agent-harness 服务未连接",
        })
    except Exception as e:
        logger.error(f"[AuditProxy] 错误: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

