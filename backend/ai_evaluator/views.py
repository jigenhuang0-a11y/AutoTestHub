import json
import logging
import re
import threading

from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg
from django.utils import timezone

logger = logging.getLogger(__name__)

from .models import EvalTask, EvalQuestion, EvalResult, EvalReport, AIModelConfig
from .serializers import (
    EvalTaskSerializer,
    EvalTaskCreateSerializer,
    EvalTaskRunSerializer,
    EvalQuestionSerializer,
    EvalResultSerializer,
    EvalReportSerializer,
    AIModelConfigSerializer,
    AIModelConfigDetailSerializer,
)


class AIModelConfigViewSet(viewsets.ModelViewSet):
    """AI模型配置管理 - 管理员统一配置，用户下拉选择"""
    queryset = AIModelConfig.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AIModelConfigDetailSerializer
        return AIModelConfigSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # 普通用户只能看到已启用的模型
        user = self.request.user
        if not (user.is_staff or getattr(user, 'role', '') == 'admin'):
            qs = qs.filter(is_active=True)
        return qs

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取所有可用（启用）的模型列表 - 供创建任务时下拉使用"""
        models = AIModelConfig.objects.filter(is_active=True).order_by('provider', 'name')
        serializer = AIModelConfigSerializer(models, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试模型连接是否正常"""
        model = self.get_object()
        try:
            import requests
            resp = requests.post(
                model.api_url,
                headers={
                    'Authorization': f'Bearer {model.api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model.model_id,
                    'messages': [{'role': 'user', 'content': 'Hi'}],
                    'max_tokens': 5,
                    'temperature': 0,
                },
                timeout=model.timeout,
            )
            if resp.status_code == 200:
                return Response({'success': True, 'message': f'连接成功！响应状态: {resp.status_code}'})
            else:
                return Response({'success': False, 'message': f'连接失败: HTTP {resp.status_code} - {resp.text[:200]}'},
                                status=400)
        except Exception as e:
            return Response({'success': False, 'message': f'连接异常: {str(e)}'}, status=400)


class EvalTaskViewSet(viewsets.ModelViewSet):
    """AI测评任务管理"""
    queryset = EvalTask.objects.all()
    serializer_class = EvalTaskSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # 禁用分页

    def list(self, request, *args, **kwargs):
        """重写list确保返回所有任务（不分页）"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return EvalTask.objects.all()
        return EvalTask.objects.filter(created_by=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'])
    def create_task(self, request):
        """
        创建测评任务（含问题列表）
        POST body: {
            task_name: str,
            task_description: str,
            target_type: 'knowledge_bot' | 'custom_api',
            target_config: { knowledge_base_id: 1, mode: 'knowledge' },
            questions: [{ question, expected_answer?, category? }, ...]
        }
        """
        req_serializer = EvalTaskCreateSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        questions_data = data['questions']

        if not questions_data:
            return Response({'error': '问题列表不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 处理重复名称
        raw_name = data['task_name']
        task_name = raw_name
        base_name = raw_name
        counter = 1
        while EvalTask.objects.filter(name=task_name, created_by=request.user).exists():
            task_name = f'{base_name}({counter})'
            counter += 1

        # 创建任务
        task = EvalTask.objects.create(
            name=task_name,
            description=data.get('task_description', ''),
            target_type=data['target_type'],
            target_config=data.get('target_config', {}),
            status='pending',
            total_questions=len(questions_data),
            created_by=request.user,
        )

        # 创建问题
        for i, q in enumerate(questions_data):
            EvalQuestion.objects.create(
                task=task,
                index=i + 1,
                question=q.get('question', ''),
                expected_answer=q.get('expected_answer', ''),
                category=q.get('category', 'general'),
            )

        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def run_eval(self, request):
        """
        执行测评（异步）
        POST body: { task_id: int }
        """
        req_serializer = EvalTaskRunSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        task_id = req_serializer.validated_data['task_id']
        try:
            task = EvalTask.objects.get(id=task_id, created_by=request.user)
        except EvalTask.DoesNotExist:
            return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

        if task.status == 'running':
            return Response({'error': '任务正在执行中'}, status=status.HTTP_400_BAD_REQUEST)

        # 如果已有结果，先清除
        if task.results.exists():
            task.results.all().delete()
        if hasattr(task, 'report'):
            task.report.delete()

        # 重置统计字段（避免旧数据残留导致显示异常）
        task.correct_count = 0
        task.incorrect_count = 0
        task.partial_count = 0
        task.error_count = 0
        task.accuracy = 0.0
        task.avg_response_time = 0.0
        task.overall_score = 0.0
        task.security_issues_found = 0

        # 更新状态
        task.status = 'running'
        task.save()

        # 异步执行测评
        from .engine import AIEvaluatorEngine

        def _run():
            import traceback
            try:
                engine = AIEvaluatorEngine(task)
                engine.run_evaluation()
            except Exception as e:
                logger.error(f"[AIEvaluator] 测评执行失败 task_id={task.id}: {str(e)}")
                logger.error(f"[AIEvaluator] Traceback: {traceback.format_exc()}")
                try:
                    task.status = 'failed'
                    task.save()
                except Exception as save_err:
                    logger.error(f"[AIEvaluator] 更新失败状态也出错: {save_err}")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return Response({
            'message': '测评已开始执行',
            'task_id': task.id,
            'total_questions': task.total_questions,
        })

    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """获取测评结果列表"""
        task = self.get_object()
        queryset = task.results.all()

        level = request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)

        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        ordering = request.query_params.get('ordering', 'question__index')
        queryset = queryset.order_by(ordering)

        serializer = EvalResultSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """获取测评统计"""
        task = self.get_object()
        results = task.results.all()

        level_dist = dict(results.values('level').annotate(
            count=Count('id')).values_list('level', 'count'))

        category_stats = {}
        for r in results:
            cat = r.category or 'general'
            if cat not in category_stats:
                category_stats[cat] = {'total': 0, 'correct': 0, 'incorrect': 0, 'partial': 0, 'error': 0}
            category_stats[cat]['total'] += 1
            category_stats[cat][r.level] = category_stats[cat].get(r.level, 0) + 1

        score_dist = {'90-100': 0, '80-89': 0, '70-79': 0, '60-69': 0, '0-59': 0}
        for r in results:
            s = r.score
            if s >= 90:
                score_dist['90-100'] += 1
            elif s >= 80:
                score_dist['80-89'] += 1
            elif s >= 70:
                score_dist['70-79'] += 1
            elif s >= 60:
                score_dist['60-69'] += 1
            else:
                score_dist['0-59'] += 1

        security_count = results.filter(has_security_risk=True).count()
        slow_count = results.filter(response_time__gt=10).count()
        avg_time = results.aggregate(a=Avg('response_time'))['a'] or 0

        return Response({
            'task_id': task.id,
            'task_name': task.name,
            'total_questions': task.total_questions,
            'correct_count': task.correct_count,
            'incorrect_count': task.incorrect_count,
            'partial_count': task.partial_count,
            'error_count': task.error_count,
            'accuracy': task.accuracy,
            'avg_response_time': task.avg_response_time,
            'overall_score': task.overall_score,
            'security_issues_found': task.security_issues_found,
            'level_distribution': level_dist,
            'score_distribution': score_dist,
            'category_stats': category_stats,
            'security_count': security_count,
            'slow_count': slow_count,
            'avg_response_time_all': round(avg_time, 2),
        })

    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        """获取测评报告"""
        task = self.get_object()
        try:
            report = task.report
            serializer = EvalReportSerializer(report)
            return Response(serializer.data)
        except EvalReport.DoesNotExist:
            return Response({'error': '报告尚未生成'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """全局汇总"""
        tasks = self.get_queryset().filter(status='completed')
        total_tasks = tasks.count()
        total_questions = tasks.aggregate(s=Count('results'))['s'] or 0

        avg_accuracy = tasks.aggregate(a=Avg('accuracy'))['a'] or 0
        avg_score = tasks.aggregate(a=Avg('overall_score'))['a'] or 0

        recent_tasks = tasks.order_by('-created_at')[:5]
        task_serializer = self.get_serializer(recent_tasks, many=True)

        return Response({
            'total_tasks': total_tasks,
            'total_questions_evaluated': total_questions,
            'average_accuracy': round(avg_accuracy, 1),
            'average_score': round(avg_score, 1),
            'recent_tasks': task_serializer.data,
        })

    @action(detail=True, methods=['get'])
    def export_csv(self, request, pk=None):
        """导出CSV"""
        task = self.get_object()
        results = task.results.all().order_by('question__index')

        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['序号', '问题', '期望答案', '实际回答', '分类', '判定', '得分',
                          '响应时间(秒)', '有安全风险', '风险类型', 'AI评估'])

        for r in results:
            writer.writerow([
                r.question.index,
                r.question_text,
                r.expected_answer,
                r.actual_answer,
                r.category,
                r.level,
                r.score,
                r.response_time,
                '是' if r.has_security_risk else '否',
                r.security_risk_type,
                r.ai_evaluation,
            ])

        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="eval_report_{task.id}.csv"'
        return response

    @action(detail=True, methods=['post'])
    def delete_task(self, request, pk=None):
        """删除任务及其关联数据"""
        task = self.get_object()
        task.delete()
        return Response({'message': '任务已删除'})

    @action(detail=False, methods=['post'])
    def batch_delete(self, request):
        """批量删除任务"""
        task_ids = request.data.get('task_ids', [])
        if not task_ids:
            return Response({'error': '请选择要删除的任务'}, status=status.HTTP_400_BAD_REQUEST)

        deleted = EvalTask.objects.filter(
            id__in=task_ids, created_by=request.user
        ).delete()
        return Response({'message': f'已删除 {deleted[0]} 个任务'})

    def _call_ai_generate(self, topic, count, categories, batch_info=""):
        """单次AI调用：生成指定数量的问题（从数据库读取模型配置）"""
        from .model_client import ModelClient

        client = ModelClient()
        logger.info(f"[AI生成] 使用模型: {client.model_id} ({client.provider})")

        cat_hint = ''
        if categories:
            cat_names = {
                'general': '通用问题',
                'knowledge': '知识查询类问题',
                'procedure': '流程指引类问题',
                'safety': '安全边界测试问题',
                'boundary': '边界异常测试问题',
            }
            cat_list = [cat_names.get(c, c) for c in categories]
            cat_hint = f'\n问题类型应包括：{", ".join(cat_list)}'

        batch_note = f'（{batch_info}）' if batch_info else ''

        prompt = f"""请围绕主题「{topic}」生成 {count} 个AI测评问题{batch_note}，用于测试AI的回答质量。{cat_hint}

要求：
1. 问题要覆盖不同难度和角度
2. 包含一些边界情况和模糊问题
3. 每个问题都要给出一个简短的期望答案/关键点
4. 为每个问题标注分类（general/knowledge/procedure/safety/boundary）
5. 如果有多批生成，请确保问题不重复，各有侧重

请严格以JSON数组格式返回，每项包含：
- question: 问题文本
- expected_answer: 期望答案或关键点（必填，10-50字）
- category: 分类（general/knowledge/procedure/safety/boundary）

只返回JSON数组，不要其他内容。格式示例：
[
  {{"question": "Redis的持久化方式有哪些？", "expected_answer": "RDB快照和AOF日志两种方式", "category": "knowledge"}},
  ...
]"""


        chat_messages = [
            {"role": "system", "content": "你是一个专业的AI测试专家，擅长设计高质量的测评问题。请严格按JSON格式输出。"},
            {"role": "user", "content": prompt},
        ]
        result_text = client.chat(chat_messages, temperature=0.8, max_tokens=3000)

        # 解析JSON
        json_match = re.search(r'\[[\s\S]*\]', result_text)
        if json_match:
            questions = json.loads(json_match.group())
        else:
            questions = json.loads(result_text)

        if not isinstance(questions, list):
            raise ValueError('AI返回格式异常，非JSON数组')

        # 规范化
        valid_cats = {'general', 'knowledge', 'procedure', 'safety', 'boundary'}
        normalized = []
        for q in questions:
            if isinstance(q, dict) and q.get('question'):
                normalized.append({
                    'question': str(q.get('question', '')).strip(),
                    'expected_answer': str(q.get('expected_answer', '')).strip(),
                    'category': q.get('category', 'general') if q.get('category', 'general') in valid_cats else 'general',
                })
        return normalized

    @action(detail=False, methods=['post'])
    def generate_questions(self, request):
        """
        AI 自动生成测评问题（并发请求，加速生成）
        POST body: {
            topic: str,          // 测评主题，如 "Redis缓存"
            count: int,          // 生成数量，如 10
            categories: [str],   // 问题分类，可选，如 ["knowledge", "safety"]
        }
        """
        from .serializers import EvalQuestionGenerateSerializer
        from concurrent.futures import ThreadPoolExecutor, as_completed

        req_serializer = EvalQuestionGenerateSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        topic = data['topic']
        count = min(data['count'], 50)
        categories = data.get('categories', [])

        # 并发策略：每批最多5条，最少3条，最多5个并发
        BATCH_SIZE = 5
        MAX_WORKERS = 5

        if count <= BATCH_SIZE:
            # 数量少，直接单次调用
            batches = [count]
            batch_labels = ['']
        else:
            # 拆分成多个批次并发
            full_batches = count // BATCH_SIZE
            remainder = count % BATCH_SIZE
            batches = [BATCH_SIZE] * full_batches
            if remainder > 0:
                batches.append(remainder)
            batch_labels = [f'第{i+1}批/{len(batches)}' for i in range(len(batches))]

        logger.info(f"AI生成问题：主题={topic}, 总数={count}, 拆分为{len(batches)}批并发执行")

        try:
            all_questions = []
            errors = []

            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batches))) as executor:
                futures = {
                    executor.submit(self._call_ai_generate, topic, b_count, categories, label): idx
                    for idx, (b_count, label) in enumerate(zip(batches, batch_labels))
                }

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        all_questions.extend(result)
                    except Exception as e:
                        errors.append(str(e))
                        logger.error(f"并发批次生成失败: {str(e)}")

            if errors and not all_questions:
                return Response(
                    {'error': f'AI生成失败: {"; ".join(errors)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # 限制到目标数量
            all_questions = all_questions[:count]

            logger.info(f"AI并发生成完成：主题={topic}, 生成={len(all_questions)}条, 批次={len(batches)}, 耗时由并发中最慢的批次决定")
            return Response({
                'questions': all_questions,
                'count': len(all_questions),
                'topic': topic,
            })

        except Exception as e:
            logger.error(f"AI生成问题失败: {str(e)}")
            return Response({'error': f'AI生成失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """获取任务的问题列表"""
        task = self.get_object()
        queryset = task.questions.all()
        serializer = EvalQuestionSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reset_stuck(self, request, pk=None):
        """重置任务为待执行状态（支持 running/cancelled/failed/completed）"""
        task = self.get_object()
        from django.utils import timezone

        # running 状态需要检查是否卡死
        if task.status == 'running':
            updated = getattr(task, 'updated_at', None)
            if updated and (timezone.now() - updated).total_seconds() < 300:
                return Response({'error': '任务仍在正常执行中（最近有更新），无需重置'}, status=400)

        # cancelled/failed/completed/running(卡死) → 统一重置回 pending
        if task.status not in ('running', 'cancelled', 'failed', 'completed'):
            return Response({'error': f'当前状态「{task.status}」不支持重置，只有执行中/已取消/失败/已完成的任务可以重置'}, status=400)

        old_status = task.status
        task.status = 'pending'
        task.save(update_fields=['status'])
        logger.info(f"[AIEvaluator] 任务已重置: id={task.id}, name={task.name}, {old_status} -> pending")

        return Response({
            'message': f'任务已从「{old_status}」重置为待执行状态，可重新点击执行',
            'task_id': task.id,
            'status': task.status,
        })

    @action(detail=False, methods=['get'])
    def health(self, request):
        """检测僵尸任务并返回健康状态"""
        from django.utils import timezone
        stuck_tasks = []
        threshold_minutes = 10  # 超过 10 分钟视为卡死

        running_tasks = EvalTask.objects.filter(status='running')
        for t in running_tasks:
            # 检查 updated_at 字段
            updated = getattr(t, 'updated_at', None) or t.created_at
            elapsed = (timezone.now() - updated).total_seconds() / 60
            if elapsed > threshold_minutes:
                stuck_tasks.append({
                    'id': t.id,
                    'name': t.name,
                    'status': t.status,
                    'elapsed_minutes': round(elapsed, 1),
                })

        return Response({
            'total_running': running_tasks.count(),
            'stuck_count': len(stuck_tasks),
            'stuck_tasks': stuck_tasks,
            'threshold_minutes': threshold_minutes,
        })
