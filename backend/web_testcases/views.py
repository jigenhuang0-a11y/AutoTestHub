import os
import shutil
import threading
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import WebTestCase, WebTestExecution
from .serializers import (
    WebTestCaseSerializer, WebTestCaseDebugSerializer, WebTestExecutionSerializer,
)


def _save_screenshot_and_record(test_case, result, user):
    """保存截图到 MEDIA 目录 + 创建执行历史记录"""
    screenshot_rel_path = ''
    src_path = result.get('screenshot_path')

    from datetime import datetime
    date_str = datetime.now().strftime('%Y%m%d')
    ts = datetime.now().strftime('%H%M%S')
    dest_base_dir = Path(settings.MEDIA_ROOT) / 'screenshots' / date_str
    dest_base_dir.mkdir(parents=True, exist_ok=True)

    if src_path and os.path.exists(src_path):
        # 最终截图: MEDIA_ROOT/screenshots/<date>/<testcase_id>_<timestamp>.png
        filename = f"{test_case.id}_{ts}.png"
        dest_path = dest_base_dir / filename
        shutil.copy2(src_path, dest_path)
        screenshot_rel_path = f"screenshots/{date_str}/{filename}"

    # 处理步骤级截图：将本地路径转为 MEDIA URL
    steps_results = result.get('steps_results', [])
    for step in steps_results:
        step_ss = step.get('screenshot')
        if step_ss and os.path.isfile(step_ss):
            try:
                # 文件名格式：step_1.png, step_2.png ...
                ss_filename = os.path.basename(step_ss)
                unique_name = f"{test_case.id}_{ts}_{ss_filename}"
                shutil.copy2(step_ss, dest_base_dir / unique_name)
                step['screenshot'] = f"/media/screenshots/{date_str}/{unique_name}"
            except Exception:
                step['screenshot'] = None

    # 创建执行历史记录
    execution = WebTestExecution.objects.create(
        test_case=test_case,
        status=result.get('status', 'error'),
        duration=result.get('duration', 0),
        result_data={
            'steps_results': steps_results,
            'assertion_errors': result.get('assertion_errors', []),
            'error': result.get('error'),
        },
        screenshot=screenshot_rel_path,
        executed_by=user,
    )

    return execution, screenshot_rel_path


class WebTestCaseViewSet(viewsets.ModelViewSet):
    """Web 自动化测试用例视图集"""
    queryset = WebTestCase.objects.all()
    serializer_class = WebTestCaseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'engine', 'browser_type']
    search_fields = ['title', 'description', 'target_url', 'ai_prompt']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            return qs
        return qs.filter(created_by=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def debug(self, request, pk=None):
        """调试执行单个 Web 用例（保存执行历史）"""
        test_case = self.get_object()

        if test_case.status == 'draft':
            return Response(
                {'error': '草稿状态用例不允许执行，请先激活'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .playwright_engine import run_web_test
        result = run_web_test(test_case, user_id=request.user.id)

        # 保存截图和执行历史
        execution, screenshot_rel = _save_screenshot_and_record(test_case, result, request.user)

        return Response({
            'execution_id': execution.id,
            'execution_result': result,
            'passed': result.get('status') == 'passed',
            'duration': result.get('duration', 0),
            'screenshot_url': f"/media/{screenshot_rel}" if screenshot_rel else None,
        })

    @action(detail=False, methods=['post'], url_path='debug-temp')
    def debug_temp(self, request):
        """临时调试：无需保存用例，直接传表单数据即可执行"""
        serializer = WebTestCaseDebugSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # 构建临时用例对象（不存数据库）
        class _TempCase:
            pass  # 动态赋值

        temp_case = _TempCase()
        for k, v in data.items():
            setattr(temp_case, k, v)
        temp_case.steps = data.get('steps') or []
        temp_case.ai_prompt = data.get('ai_prompt') or ''
        temp_case.assertions = data.get('assertions') or []
        temp_case.screenshot_enabled = data.get('screenshot_enabled', True)
        temp_case.full_page_screenshot = data.get('full_page_screenshot', False)
        temp_case.record_video = data.get('record_video', False)
        temp_case.cookies = data.get('cookies') or []
        temp_case.viewport = {}
        temp_case.title = '临时调试'

        try:
            from .playwright_engine import run_web_test
            result = run_web_test(temp_case, user_id=request.user.id)

            # 临时调试也保存截图到 MEDIA（不关联用例）
            screenshot_url = None
            src_path = result.get('screenshot_path')
            if src_path and os.path.exists(src_path):
                from datetime import datetime
                date_str = datetime.now().strftime('%Y%m%d')
                ts = datetime.now().strftime('%H%M%S')
                filename = f"temp_{ts}.png"
                dest_dir = Path(settings.MEDIA_ROOT) / 'screenshots' / date_str
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_dir / filename)
                screenshot_url = f"/media/screenshots/{date_str}/{filename}"

            # 调试模式：步骤截图路径转 URL
            for step in result.get('steps_results', []):
                ss_path = step.get('screenshot')
                if ss_path and os.path.isfile(ss_path):
                    try:
                        date_str_d = datetime.now().strftime('%Y%m%d')
                        ts_d = datetime.now().strftime('%H%M%S')
                        ss_name = os.path.basename(ss_path)
                        unique_name = f"temp_{ts_d}_{ss_name}"
                        dest_ddir = Path(settings.MEDIA_ROOT) / 'screenshots' / date_str_d
                        dest_ddir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(ss_path, dest_ddir / unique_name)
                        step['screenshot'] = f"/media/screenshots/{date_str_d}/{unique_name}"
                    except Exception:
                        step['screenshot'] = None

            return Response({
                'execution_result': result,
                'passed': result.get('status') == 'passed',
                'duration': result.get('duration', 0),
                'screenshot_url': screenshot_url,
            })
        except Exception as e:
            return Response(
                {'error': f'调试执行失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='executions')
    def executions(self, request, pk=None):
        """获取某个用例的执行历史"""
        test_case = self.get_object()
        qs = WebTestExecution.objects.filter(test_case=test_case).order_by('-executed_at')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = WebTestExecutionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = WebTestExecutionSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='screenshot-download')
    def screenshot_download(self, request, pk=None):
        """下载某次执行的截图"""
        execution_id = request.query_params.get('execution_id')
        if not execution_id:
            return Response({'error': '缺少 execution_id'}, status=400)

        try:
            execution = WebTestExecution.objects.get(
                id=execution_id, test_case_id=pk
            )
        except WebTestExecution.DoesNotExist:
            raise Http404('执行记录不存在')

        if not execution.screenshot:
            raise Http404('该次执行没有截图')

        file_path = Path(settings.MEDIA_ROOT) / execution.screenshot
        if not file_path.exists():
            raise Http404(f'截图文件不存在: {file_path}')

        filename = f"{execution.test_case.title}_{execution.executed_at.strftime('%Y%m%d_%H%M%S')}.png"
        response = FileResponse(open(file_path, 'rb'), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class WebTestExecutionListView(APIView):
    """全局 Web 执行记录列表（供执行历史页面统一展示，支持批量删除）"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = WebTestExecution.objects.select_related('test_case', 'executed_by').order_by('-executed_at')
        # 筛选
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(test_case__title__icontains=search)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        # 分页
        page_size = int(request.query_params.get('page_size', 20))
        page_num = int(request.query_params.get('page', 1))
        from django.core.paginator import Paginator
        paginator = Paginator(qs, page_size)
        page_obj = paginator.page(page_num)
        serializer = WebTestExecutionSerializer(page_obj.object_list, many=True)
        return Response({
            'count': paginator.count,
            'results': serializer.data,
            'next': page_obj.has_next() and f'?page={page_num + 1}&page_size={page_size}' or None,
            'previous': page_num > 1 and f'?page={page_num - 1}&page_size={page_size}' or None,
        })

    def post(self, request):
        """批量删除执行记录"""
        ids = request.data.get('ids', [])
        if not isinstance(ids, list) or len(ids) == 0:
            return Response({'error': '请提供要删除的记录 ID 列表'}, status=400)
        deleted_count, _ = WebTestExecution.objects.filter(id__in=ids).delete()
        return Response({'detail': f'成功删除 {deleted_count} 条记录'})


class WebTestExecutionDetailView(APIView):
    """Web 执行记录详情 / 删除"""
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(WebTestExecution, pk=pk)

    def get(self, request, pk):
        obj = self.get_object(pk)
        serializer = WebTestExecutionSerializer(obj)
        return Response(serializer.data)

    def delete(self, request, pk):
        obj = self.get_object(pk)
        obj.delete()
        return Response({'detail': '删除成功'})

    def post(self, request, pk):
        """重新执行（重跑）——异步后台执行，立即返回（在原记录上更新）"""
        execution = self.get_object(pk)

        test_case = execution.test_case
        if not test_case:
            return Response(
                {'error': '该执行记录未关联用例，无法重跑'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if test_case.status == 'draft':
            return Response(
                {'error': '关联用例处于草稿状态，无法执行'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 重置原记录状态为 running，更新时间确保列表排序置顶
        execution.status = 'running'
        execution.duration = 0
        execution.result_data = {}
        execution.screenshot = ''
        execution.executed_by = request.user
        execution.executed_at = timezone.now()
        execution.save()

        # 异步在后台线程执行
        user_id = request.user.id
        exec_id = execution.id

        def _run_and_save():
            try:
                from .playwright_engine import run_web_test
                result = run_web_test(test_case, user_id=user_id)

                # 处理截图
                screenshot_rel = ''
                from datetime import datetime
                date_str = datetime.now().strftime('%Y%m%d')
                ts = datetime.now().strftime('%H%M%S')
                dest_base_dir = Path(settings.MEDIA_ROOT) / 'screenshots' / date_str
                dest_base_dir.mkdir(parents=True, exist_ok=True)

                src_path = result.get('screenshot_path')
                if src_path and os.path.exists(src_path):
                    filename = f"{test_case.id}_{ts}.png"
                    dest_path = dest_base_dir / filename
                    shutil.copy2(src_path, dest_path)
                    screenshot_rel = f"screenshots/{date_str}/{filename}"

                # 处理步骤级截图
                steps_results = result.get('steps_results', [])
                for step in steps_results:
                    step_ss = step.get('screenshot')
                    if step_ss and os.path.isfile(step_ss):
                        try:
                            ss_filename = os.path.basename(step_ss)
                            unique_name = f"{test_case.id}_{ts}_{ss_filename}"
                            shutil.copy2(step_ss, dest_base_dir / unique_name)
                            step['screenshot'] = f"/media/screenshots/{date_str}/{unique_name}"
                        except Exception:
                            step['screenshot'] = None

                # 更新执行记录（原记录）
                WebTestExecution.objects.filter(id=exec_id).update(
                    status=result.get('status', 'error'),
                    duration=result.get('duration', 0),
                    result_data={
                        'steps_results': steps_results,
                        'assertion_errors': result.get('assertion_errors', []),
                        'error': result.get('error'),
                    },
                    screenshot=screenshot_rel,
                )
            except Exception as e:
                WebTestExecution.objects.filter(id=exec_id).update(
                    status='error',
                    result_data={'error': str(e)},
                )

        thread = threading.Thread(target=_run_and_save, daemon=True)
        thread.start()

        return Response({
            'execution_id': execution.id,
            'status': 'running',
            'detail': '测试已提交后台执行',
        })
