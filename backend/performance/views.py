"""
性能测试模块 — API 视图
PerfTestCaseViewSet:     用例 CRUD
PerfExecuteView:         触发执行
PerfExecutionListView:   执行历史列表
PerfExecutionDetailView: 执行详情
PerfExecutionStopView:   停止执行
PerfExecutionMetricsView:实时指标
"""
import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from .models import PerfTestCase, PerfExecution
from .serializers import (
    PerfTestCaseSerializer,
    PerfExecutionSerializer,
    PerfExecutionCreateSerializer,
)
from .engine import PerfTestEngine
from .ai_analyzer import PerfAIAnalyzer

logger = logging.getLogger(__name__)

# 全局引擎注册表，用于停止执行
_running_engines = {}


class PerfTestCaseViewSet(viewsets.ModelViewSet):
    """性能测试用例 CRUD"""
    queryset = PerfTestCase.objects.all()
    serializer_class = PerfTestCaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            qs = super().get_queryset()
            # 支持筛选
            status_filter = self.request.query_params.get('status')
            if status_filter:
                qs = qs.filter(status=status_filter)
            method_filter = self.request.query_params.get('method')
            if method_filter:
                qs = qs.filter(method=method_filter.upper())
            search = self.request.query_params.get('search')
            if search:
                from django.db.models import Q
                qs = qs.filter(Q(name__icontains=search) | Q(target_url__icontains=search))
            return qs
        except Exception as e:
            import traceback
            logger.error(f"get_queryset error: {e}\n{traceback.format_exc()}")
            raise

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            import traceback
            logger.error(f"list error: {e}\n{traceback.format_exc()}")
            return Response({'detail': str(e), 'traceback': traceback.format_exc()}, status=500)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def executions(self, request, pk=None):
        """获取某个用例的所有执行记录"""
        test_case = self.get_object()
        executions = test_case.executions.all()
        serializer = PerfExecutionSerializer(executions, many=True)
        return Response(serializer.data)


class PerfExecuteView(APIView):
    """触发性能测试执行"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PerfExecutionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_case_id = serializer.validated_data['test_case_id']
        test_case = get_object_or_404(PerfTestCase, id=test_case_id)

        execution_id = serializer.validated_data.get('execution_id')
        if execution_id:
            # 重跑模式：复用原记录，重置状态
            execution = get_object_or_404(
                PerfExecution, id=execution_id, test_case=test_case
            )
            execution.status = 'running'
            execution.total_requests = 0
            execution.requests_per_second = 0
            execution.failures = 0
            execution.avg_response_time = 0
            execution.min_response_time = 0
            execution.max_response_time = 0
            execution.p50_response_time = 0
            execution.p90_response_time = 0
            execution.p95_response_time = 0
            execution.p99_response_time = 0
            execution.metrics_timeline = []
            execution.thresholds_passed = True
            execution.threshold_errors = []
            execution.execution_log = ''
            execution.started_at = timezone.now()
            execution.completed_at = None
            execution.save()
        else:
            # 创建新执行记录
            execution = PerfExecution.objects.create(
                test_case=test_case,
                test_type=test_case.test_type,
                status='running',
                users=test_case.users,
                duration=test_case.duration,
                started_by=request.user,
                started_at=timezone.now(),
            )

        # 异步启动引擎
        engine = PerfTestEngine(execution)
        _running_engines[execution.id] = engine
        engine.run_async()

        result = PerfExecutionSerializer(execution)
        return Response(result.data, status=status.HTTP_201_CREATED)


class PerfExecutionListView(APIView):
    """执行历史列表（带分页）"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        executions = PerfExecution.objects.select_related('test_case', 'started_by').all()

        # 筛选
        test_case_id = request.query_params.get('test_case_id')
        if test_case_id:
            executions = executions.filter(test_case_id=test_case_id)
        status_filter = request.query_params.get('status')
        if status_filter:
            executions = executions.filter(status=status_filter)
        test_type_filter = request.query_params.get('test_type')
        if test_type_filter:
            executions = executions.filter(test_type=test_type_filter)
        started_by = request.query_params.get('started_by')
        if started_by:
            executions = executions.filter(started_by_id=started_by)
        search = request.query_params.get('search')
        if search:
            from django.db.models import Q
            executions = executions.filter(
                Q(test_case__name__icontains=search) | Q(execution_log__icontains=search)
            )
        # 排除套件触发产生的记录（只看手动执行）
        exclude_suite = request.query_params.get('exclude_suite')
        if exclude_suite and exclude_suite.lower() in ('true', '1', 'yes'):
            executions = executions.filter(suite_execution__isnull=True)


        # 分页
        paginator = PageNumberPagination()
        paginator.page_size = request.query_params.get('page_size', 10)
        result_page = paginator.paginate_queryset(executions, request)
        serializer = PerfExecutionSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def delete(self, request, pk=None):
        """删除单条执行记录"""
        execution = get_object_or_404(PerfExecution, pk=pk)
        execution.delete()
        return Response({'message': '已删除'}, status=status.HTTP_204_NO_CONTENT)


class PerfExecutionDetailView(APIView):
    """执行详情（含实时指标）"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        execution = get_object_or_404(
            PerfExecution.objects.select_related('test_case', 'started_by'),
            pk=pk
        )
        serializer = PerfExecutionSerializer(execution)
        return Response(serializer.data)

    def delete(self, request, pk):
        execution = get_object_or_404(PerfExecution, pk=pk)
        execution.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PerfExecutionStopView(APIView):
    """停止正在执行的压测"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        execution = get_object_or_404(PerfExecution, pk=pk)

        if execution.status != 'running':
            return Response(
                {'error': '只有执行中的压测才能停止'},
                status=status.HTTP_400_BAD_REQUEST
            )

        engine = _running_engines.get(execution.id)
        if engine and engine.is_running():
            engine.stop()
            # 引擎会在内部更新状态为 stopped
            return Response({'message': '已发送停止信号，等待压测终止...'})
        else:
            # 引擎可能已结束或未注册，直接标记
            execution.status = 'stopped'
            execution.completed_at = timezone.now()
            execution.execution_log += '\n[INFO] 用户手动停止了压测（引擎已结束）'
            execution.save()
            return Response({'message': '压测已停止'})


class PerfExecutionMetricsView(APIView):
    """获取最新的实时指标（轮询用）"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            execution = get_object_or_404(PerfExecution, pk=pk)
            return Response({
                'id': execution.id,
                'status': execution.status,
                'status_display': execution.get_status_display(),
                'total_requests': execution.total_requests,
                'requests_per_second': execution.requests_per_second,
                'failures': execution.failures,
                'p50_response_time': execution.p50_response_time,
                'p95_response_time': execution.p95_response_time,
                'p99_response_time': execution.p99_response_time,
                'avg_response_time': execution.avg_response_time,
                'metrics_timeline': execution.metrics_timeline,
                'thresholds_passed': execution.thresholds_passed,
                'threshold_errors': execution.threshold_errors,
                'exec_summary': execution.exec_summary,
            })
        except Exception as e:
            import traceback
            logger.error(f"metrics error: {e}\n{traceback.format_exc()}")
            return Response({'detail': str(e), 'traceback': traceback.format_exc()}, status=500)


class PerfExecutionDiagnoseView(APIView):
    """手动触发 AI 性能诊断"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        execution = get_object_or_404(
            PerfExecution.objects.select_related('test_case'),
            pk=pk
        )

        if execution.status not in ('completed', 'failed'):
            return Response(
                {'error': '只有已完成或失败的执行才能触发诊断'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not execution.total_requests:
            return Response(
                {'error': '执行没有产生数据，无法诊断'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 异步执行 AI 诊断
        PerfAIAnalyzer.analyze_async(execution)

        return Response({
            'message': 'AI 诊断已触发，正在分析中...',
            'status': 'diagnosing',
        })

