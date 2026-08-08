from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Q
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

from .models import QualityCheckTask, QualityCheckResult, QualityStandard
from .serializers import (
    QualityCheckTaskSerializer,
    QualityCheckResultSerializer,
    QualityStandardSerializer,
    QualityCheckRequestSerializer,
    QualityTaskSummarySerializer,
)
from .engine import QualityCheckEngine


class QualityCheckTaskViewSet(viewsets.ModelViewSet):
    """质检任务管理"""
    queryset = QualityCheckTask.objects.all()
    serializer_class = QualityCheckTaskSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # 禁用分页，前端自行处理

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return QualityCheckTask.objects.all()
        return QualityCheckTask.objects.filter(created_by=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'])
    def run_check(self, request):
        """执行质检"""
        req_serializer = QualityCheckRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data
        testcases = data['testcases']
        scenario = data.get('scenario', 'general')

        if not testcases:
            return Response({'error': '用例列表不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 创建任务（重复名称自动加递增后缀）
        raw_name = data.get('task_name') or ''
        task_name = raw_name if raw_name else f'质检任务_{timezone.now().strftime("%Y%m%d_%H%M%S")}'
        if raw_name:
            base_name = raw_name
            counter = 1
            while QualityCheckTask.objects.filter(name=task_name, created_by=request.user).exists():
                task_name = f'{base_name}({counter})'
                counter += 1

        task = QualityCheckTask.objects.create(
            name=task_name,
            description=data.get('task_description', ''),
            scenario=scenario,
            status='processing',
            total_cases=len(testcases),
            check_duplicates=data.get('check_duplicates', True),
            check_completeness=data.get('check_completeness', True),
            check_format=data.get('check_format', True),
            check_content_quality=data.get('check_content_quality', True),
            duplicate_threshold=data.get('duplicate_threshold', 0.85),
            created_by=request.user,
        )

        try:
            # 执行质检
            engine = QualityCheckEngine(
                scenario=scenario,
                check_duplicates=task.check_duplicates,
                check_completeness=task.check_completeness,
                check_format=task.check_format,
                check_content_quality=task.check_content_quality,
                duplicate_threshold=task.duplicate_threshold,
            )
            results = engine.run_check(testcases)

            # 保存结果
            passed = warning = failed = 0
            total_score = 0
            for r in results:
                QualityCheckResult.objects.create(
                    task=task,
                    case_id=r['case_id'],
                    case_title=r['case_title'],
                    case_content=r['case_content'],
                    score=r['score'],
                    level=r['level'],
                    completeness_score=r['completeness_score'],
                    format_score=r['format_score'],
                    content_score=r['content_score'],
                    issues=r['issues'],
                    suggestions=r['suggestions'],
                    duplicate_of=r['duplicate_of'],
                    duplicate_similarity=r['duplicate_similarity'],
                )
                if r['level'] == 'pass':
                    passed += 1
                elif r['level'] == 'warning':
                    warning += 1
                else:
                    failed += 1
                total_score += r['score']

            # 更新任务统计
            task.passed_cases = passed
            task.warning_cases = warning
            task.failed_cases = failed
            # 综合评分 = 结构质量分 * 0.4 + 通过率 * 0.6
            # 通过率 = (passed + warning) / total，warning 也算可用用例
            structure_score = round(total_score / len(results), 1) if results else 0
            pass_rate = round((passed + warning) / len(results) * 100, 1) if results else 0
            task.overall_score = round(structure_score * 0.4 + pass_rate * 0.6, 1)
            task.pass_rate = pass_rate
            task.status = 'completed'
            task.save()

            task_serializer = self.get_serializer(task)
            return Response(task_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f'质检失败: {str(e)}')
            task.status = 'failed'
            task.save()
            return Response({'error': f'质检失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """获取任务的质检结果列表"""
        task = self.get_object()
        queryset = task.results.all()

        # 按等级筛选
        level = request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)

        # 排序
        ordering = request.query_params.get('ordering', '-score')
        queryset = queryset.order_by(ordering)

        serializer = QualityCheckResultSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """获取任务统计信息"""
        task = self.get_object()
        results = task.results.all()

        # 等级分布
        level_dist = dict(results.values('level').annotate(count=Count('id')).values_list('level', 'count'))

        # 分数分布
        score_ranges = {'90-100': 0, '80-89': 0, '70-79': 0, '60-69': 0, '0-59': 0}
        for r in results:
            s = r.score
            if s >= 90: score_ranges['90-100'] += 1
            elif s >= 80: score_ranges['80-89'] += 1
            elif s >= 70: score_ranges['70-79'] += 1
            elif s >= 60: score_ranges['60-69'] += 1
            else: score_ranges['0-59'] += 1

        # 问题类型分布
        issue_types = {}
        for r in results:
            for issue in (r.issues or []):
                t = issue.get('type', 'unknown')
                issue_types[t] = issue_types.get(t, 0) + 1

        return Response({
            'task_id': task.id,
            'task_name': task.name,
            'total_cases': task.total_cases,
            'passed_cases': task.passed_cases,
            'warning_cases': task.warning_cases,
            'failed_cases': task.failed_cases,
            'overall_score': task.overall_score,
            'pass_rate': task.pass_rate,
            'level_distribution': level_dist,
            'score_distribution': score_ranges,
            'issue_type_distribution': issue_types,
            'top_issues': sorted(issue_types.items(), key=lambda x: x[1], reverse=True)[:10],
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """全局质检汇总"""
        tasks = self.get_queryset().filter(status='completed')
        total_tasks = tasks.count()
        total_cases = tasks.aggregate(s=Count('results'))['s'] or 0

        recent_tasks = tasks.order_by('-created_at')[:5]
        task_serializer = self.get_serializer(recent_tasks, many=True)

        # 等级分布（所有任务）
        all_results = QualityCheckResult.objects.filter(task__in=tasks)
        level_dist = dict(all_results.values('level').annotate(
            count=Count('id')).values_list('level', 'count'))

        # 平均分
        avg_score = tasks.aggregate(a=Avg('overall_score'))['a'] or 0

        # 整体通过率（pass + warning 都算通过）
        total_all = all_results.count()
        total_pass = all_results.filter(level__in=['pass', 'warning']).count()
        pass_rate = round(total_pass / total_all * 100, 1) if total_all else 0

        return Response({
            'total_tasks': total_tasks,
            'total_cases_checked': total_cases,
            'average_score': round(avg_score, 1),
            'pass_rate': pass_rate,
            'recent_tasks': task_serializer.data,
            'level_distribution': level_dist,
        })

    @action(detail=False, methods=['post'])
    def export_report(self, request):
        """导出质检报告"""
        task_id = request.data.get('task_id')
        if not task_id:
            return Response({'error': '请指定任务ID'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            task = self.get_object()
        except:
            return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

        results = task.results.all().order_by('-score')
        result_serializer = QualityCheckResultSerializer(results, many=True)

        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['用例编号', '用例标题', '总分', '等级', '完整性得分', '格式得分', '内容得分',
                          '问题列表', '优化建议', '疑似重复'])
        for r in results:
            issues_str = '; '.join([i.get('message', '') for i in (r.issues or [])])
            suggestions_str = '; '.join([s.get('message', '') for s in (r.suggestions or [])])
            writer.writerow([r.case_id, r.case_title, r.score, r.level,
                             r.completeness_score, r.format_score, r.content_score,
                             issues_str, suggestions_str, r.duplicate_of])

        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="quality_report_{task.id}.csv"'
        return response


class QualityStandardViewSet(viewsets.ModelViewSet):
    """质检标准管理"""
    queryset = QualityStandard.objects.all()
    serializer_class = QualityStandardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = QualityStandard.objects.all()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs

    @action(detail=False, methods=['post'])
    def init_defaults(self, request):
        """初始化默认质检标准"""
        defaults = [
            {
                'name': '标题完整性', 'rule_type': 'completeness', 'weight': 1.0,
                'description': '检查用例是否包含清晰明确的标题',
                'check_points': ['标题字段非空', '标题长度≥5字'],
                'deduction_rules': {'missing': -10, 'too_short': -3, 'vague': -5},
            },
            {
                'name': '步骤完整性', 'rule_type': 'completeness', 'weight': 1.5,
                'description': '检查测试步骤是否完整',
                'check_points': ['步骤字段非空', '步骤数≥2', '步骤有编号'],
                'deduction_rules': {'missing': -15, 'too_few': -5, 'no_number': -3},
            },
            {
                'name': '预期结果完整性', 'rule_type': 'completeness', 'weight': 1.5,
                'description': '检查预期结果是否完整',
                'check_points': ['预期结果非空', '描述具体明确'],
                'deduction_rules': {'missing': -15, 'too_short': -3},
            },
            {
                'name': '内容质量', 'rule_type': 'content', 'weight': 2.0,
                'description': '检查用例内容质量和验证点覆盖',
                'check_points': ['有明确验证条件', '考虑边界场景', '考虑异常场景'],
                'deduction_rules': {'no_verification': -10, 'no_boundary': -3, 'no_error': -3},
            },
            {
                'name': '格式规范', 'rule_type': 'format', 'weight': 1.0,
                'description': '检查用例格式规范性',
                'check_points': ['标题格式规范', '步骤格式规范', '结果描述规范'],
                'deduction_rules': {'title_vague': -5, 'steps_no_format': -3},
            },
            {
                'name': '重复检测', 'rule_type': 'duplicate', 'weight': 1.0,
                'description': '检测重复或高度相似的用例',
                'check_points': ['相似度阈值≥0.85'],
                'deduction_rules': {'duplicate': -15},
            },
        ]

        created = []
        for d in defaults:
            obj, is_new = QualityStandard.objects.get_or_create(
                name=d['name'], defaults=d
            )
            if is_new:
                created.append(obj.name)

        return Response({
            'message': f'初始化完成，新增{len(created)}条标准',
            'created': created,
        })
