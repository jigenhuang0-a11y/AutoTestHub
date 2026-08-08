from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import TestSuite
from .serializers import TestSuiteSerializer


class TestSuiteViewSet(viewsets.ModelViewSet):
    """测试套件视图集 - 用例的集合/文件夹"""

    permission_classes = [IsAuthenticated]
    serializer_class = TestSuiteSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            queryset = TestSuite.objects.all()
        else:
            queryset = TestSuite.objects.filter(created_by=user)
        
        # 搜索过滤：套件名称或描述
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search) | queryset.filter(description__icontains=search)
        
        # 用例数范围过滤
        cases_count = self.request.query_params.get('cases_count')
        if cases_count:
            if cases_count == '1-5':
                queryset = queryset.annotate(case_count=models.Count('test_cases')).filter(case_count__gte=1, case_count__lte=5)
            elif cases_count == '6-10':
                queryset = queryset.annotate(case_count=models.Count('test_cases')).filter(case_count__gte=6, case_count__lte=10)
            elif cases_count == '11-20':
                queryset = queryset.annotate(case_count=models.Count('test_cases')).filter(case_count__gte=11, case_count__lte=20)
            elif cases_count == '20+':
                queryset = queryset.annotate(case_count=models.Count('test_cases')).filter(case_count__gt=20)
        
        # 日期范围过滤
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行套件中的所有用例（异步启动，立即返回 execution_id）"""
        import threading
        suite = self.get_object()
        environment = request.data.get('environment', 'dev')

        from execution.engine import TestExecutionEngine
        from execution.models import TestExecution
        from django.utils import timezone

        now = timezone.now()
        execution_name = request.data.get('name', f'{suite.name} - {now.strftime("%Y/%m/%d %H:%M")}')

        # 合并 API + Web + 性能用例ID
        all_ids = suite.get_total_case_ids()
        api_count = len(suite.test_cases or [])
        web_count = len(suite.web_test_cases or [])
        perf_count = len(suite.perf_test_cases or [])

        # 创建执行记录 - 关联套件
        execution = TestExecution.objects.create(
            name=execution_name,
            test_suite=suite,
            test_cases=suite.test_cases,
            web_test_cases=suite.web_test_cases,
            perf_test_cases=suite.perf_test_cases,
            total_count=len(all_ids),
            trigger_type='manual_suite',
            environment=environment,
            status='pending',
            started_by=request.user,
            execution_log=f"[INFO] 用例总数: {len(all_ids)} (API: {api_count}, Web: {web_count}, 性能: {perf_count})\n"
        )

        # 从 suite_vars 中提取全局变量（手动配置的固定值）
        global_vars = {}
        if suite.suite_vars and 'global_vars' in suite.suite_vars:
            for var in suite.suite_vars['global_vars']:
                if var.get('name') and var.get('value'):
                    global_vars[var['name']] = var['value']

        def _run_async(execution_id, global_vars, suite_obj):
            """后台线程执行测试"""
            try:
                engine = TestExecutionEngine(execution_id, global_variables=global_vars)
                engine.execute()
                # 更新套件执行次数
                suite_obj.execution_count = (suite_obj.execution_count or 0) + 1
                suite_obj.save(update_fields=['execution_count'])
            except Exception as e:
                import traceback
                traceback.print_exc()
                try:
                    exc = TestExecution.objects.get(id=execution_id)
                    exc.status = 'failed'
                    exc.execution_log = f"[ERROR] {str(e)}"
                    exc.save()
                except Exception:
                    pass

        thread = threading.Thread(
            target=_run_async,
            args=(execution.id, global_vars, suite),
            daemon=True
        )
        thread.start()

        return Response({
            'execution_id': execution.id,
            'status': 'running',
            'message': '执行已启动，请通过执行历史查看结果'
        })
    def schedule_execute(self, request, pk=None):
        """创建或更新定时执行任务"""
        from execution.models import TestExecution
        from django.utils import timezone
        from datetime import datetime as dt

        suite = self.get_object()
        all_ids = suite.get_total_case_ids()
        if not all_ids:
            return Response({'error': '该套件中没有测试用例,请先添加用例'}, status=status.HTTP_400_BAD_REQUEST)

        schedule_id = request.data.get('schedule_id')
        locked = request.data.get('locked', False)

        # --- 更新模式 ---
        if schedule_id:
            try:
                schedule = TestExecution.objects.get(
                    id=schedule_id, test_suite=suite,
                    trigger_type='scheduled', status='pending'
                )
            except TestExecution.DoesNotExist:
                return Response({'error': '定时任务不存在或已完成/已取消'}, status=status.HTTP_404_NOT_FOUND)

            # 仅设置人可修改
            if schedule.started_by != request.user:
                return Response({'error': '只有设置人可以修改此定时任务'}, status=status.HTTP_403_FORBIDDEN)

            if 'scheduled_at' in request.data:
                try:
                    new_time = dt.strptime(request.data['scheduled_at'], '%Y-%m-%d %H:%M')
                    new_time = timezone.make_aware(new_time)
                    if new_time < timezone.now():
                        return Response({'error': '计划执行时间不能早于当前时间'}, status=status.HTTP_400_BAD_REQUEST)
                    schedule.scheduled_at = new_time
                    schedule.name = f'[定时] {suite.name} - {new_time.strftime("%m/%d %H:%M")}'
                except ValueError:
                    return Response({'error': '时间格式错误，请使用 YYYY-MM-DD HH:MM 格式'}, status=status.HTTP_400_BAD_REQUEST)

            if 'environment' in request.data:
                schedule.environment = request.data['environment']
            if 'locked' in request.data:
                schedule.locked = request.data['locked']

            schedule.save()
            return Response({
                'message': f'定时任务已更新, 将在 {schedule.scheduled_at.strftime("%Y-%m-%d %H:%M")} 自动执行',
                'execution_id': schedule.id,
                'scheduled_at': schedule.scheduled_at.isoformat(),
                'locked': schedule.locked,
            })

        # --- 创建模式 ---
        # 检查是否已有待执行的定时任务
        existing = TestExecution.objects.filter(
            test_suite=suite, trigger_type='scheduled', status='pending'
        ).first()
        if existing and not request.data.get('force'):
            return Response({
                'error': '该套件已有待执行的定时任务',
                'existing_schedule': {
                    'id': existing.id,
                    'scheduled_at': existing.scheduled_at.isoformat() if existing.scheduled_at else None,
                    'environment': existing.environment,
                    'locked': existing.locked,
                    'started_by_id': existing.started_by_id,
                    'started_by_username': existing.started_by.username if existing.started_by else None,
                }
            }, status=status.HTTP_409_CONFLICT)

        # 如果 force，取消已有任务
        if existing:
            existing.status = 'cancelled'
            existing.save(update_fields=['status'])

        scheduled_at_str = request.data.get('scheduled_at')
        if not scheduled_at_str:
            return Response({'error': '缺少计划执行时间 (scheduled_at)'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            scheduled_at = dt.strptime(scheduled_at_str, '%Y-%m-%d %H:%M')
            scheduled_at = timezone.make_aware(scheduled_at)
        except ValueError:
            return Response({'error': '时间格式错误，请使用 YYYY-MM-DD HH:MM 格式'}, status=status.HTTP_400_BAD_REQUEST)

        if scheduled_at < timezone.now():
            return Response({'error': '计划执行时间不能早于当前时间'}, status=status.HTTP_400_BAD_REQUEST)

        environment = request.data.get('environment', 'dev')
        execution_name = f'[定时] {suite.name} - {scheduled_at.strftime("%m/%d %H:%M")}'

        execution = TestExecution.objects.create(
            name=execution_name,
            test_suite=suite,
            test_cases=suite.test_cases,
            web_test_cases=suite.web_test_cases,
            total_count=len(all_ids),
            trigger_type='scheduled',
            environment=environment,
            status='pending',
            started_by=request.user,
            scheduled_at=scheduled_at,
            locked=locked,
        )

        return Response({
            'message': f'定时任务已创建，将在 {scheduled_at.strftime("%Y-%m-%d %H:%M")} 自动执行',
            'execution_id': execution.id,
            'scheduled_at': scheduled_at.isoformat(),
            'locked': locked,
        })

    @action(detail=True, methods=['post'], url_path='cancel-schedule')
    def cancel_schedule(self, request, pk=None):
        """取消定时任务（仅设置人可取消）"""
        from execution.models import TestExecution

        suite = self.get_object()
        schedule_id = request.data.get('schedule_id')
        try:
            schedule = TestExecution.objects.get(
                id=schedule_id, test_suite=suite,
                trigger_type='scheduled', status='pending'
            )
        except TestExecution.DoesNotExist:
            return Response({'error': '定时任务不存在或已完成/已取消'}, status=status.HTTP_404_NOT_FOUND)

        if schedule.started_by != request.user:
            return Response({'error': '只有设置人可以取消此定时任务'}, status=status.HTTP_403_FORBIDDEN)

        schedule.status = 'cancelled'
        schedule.save(update_fields=['status'])

        return Response({
            'message': '定时任务已取消',
            'execution_id': schedule.id,
        })

    @action(detail=True, methods=['post'], url_path='toggle-lock')
    def toggle_lock(self, request, pk=None):
        """切换定时任务锁定状态（仅设置人）"""
        from execution.models import TestExecution

        suite = self.get_object()
        schedule_id = request.data.get('schedule_id')
        try:
            # 允许对任何状态的定时任务操作解锁/锁定（不再限制 pending）
            schedule = TestExecution.objects.get(
                id=schedule_id, test_suite=suite,
                trigger_type='scheduled',
            )
        except TestExecution.DoesNotExist:
            return Response({'error': '定时任务不存在'}, status=status.HTTP_404_NOT_FOUND)

        if schedule.started_by != request.user:
            return Response({'error': '只有设置人可以锁定/解锁定时任务'}, status=status.HTTP_403_FORBIDDEN)

        # 如果任务已经在运行中，不允许再锁定了（但允许解锁）
        if schedule.locked and schedule.status == 'running':
            return Response({'error': '任务正在运行中，无法修改锁定状态'}, status=status.HTTP_409_CONFLICT)

        schedule.locked = not schedule.locked
        schedule.save(update_fields=['locked'])

        return Response({
            'message': f'定时任务已{"锁定" if schedule.locked else "解锁"}',
            'execution_id': schedule.id,
            'locked': schedule.locked,
        })

    @action(detail=True, methods=['post'], url_path='add-test-cases')
    def add_test_cases(self, request, pk=None):
        """向套件中批量添加测试用例"""
        suite = self.get_object()
        test_case_ids = request.data.get('test_case_ids', [])
        if not test_case_ids:
            return Response({'error': '缺少测试用例ID列表'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 追加并去重
        current_ids = list(suite.test_cases) if suite.test_cases else []
        added = 0
        for tcid in test_case_ids:
            if tcid not in current_ids:
                current_ids.append(tcid)
                added += 1
        suite.test_cases = current_ids
        suite.save(update_fields=['test_cases', 'updated_at'])
        
        return Response({
            'message': f'成功添加 {added} 个测试用例',
            'added_count': added,
            'total_count': len(current_ids),
        })

    @action(detail=True, methods=['post'])
    def execute_with_dataset(self, request, pk=None):
        """使用数据集执行套件"""
        suite = self.get_object()
        dataset_id = request.data.get('dataset_id')
        
        if not dataset_id:
            return Response({'error': '缺少数据集ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取数据集
        try:
            from data_factory.models import DataFactoryDataset, DataFactoryRecord
            dataset = DataFactoryDataset.objects.get(id=dataset_id)
            records = DataFactoryRecord.objects.filter(dataset=dataset)[:10]  # 限制最多10条记录
        except DataFactoryDataset.DoesNotExist:
            return Response({'error': '数据集不存在'}, status=status.HTTP_404_NOT_FOUND)
        
        if not records.exists():
            return Response({'error': '数据集中没有记录'}, status=status.HTTP_400_BAD_REQUEST)
        
        environment = request.data.get('environment', 'dev')
        
        from execution.engine import TestExecutionEngine
        from execution.models import TestExecution
        from django.utils import timezone
        
        now = timezone.now()
        execution_name = request.data.get('name', f'{suite.name} (数据集: {dataset.name}) - {now.strftime("%Y/%m/%d %H:%M")}')
        
        # 创建执行记录
        all_case_ids = suite.get_total_case_ids()
        execution = TestExecution.objects.create(
            name=execution_name,
            test_suite=suite,
            test_cases=suite.test_cases,
            web_test_cases=suite.web_test_cases,
            total_count=len(all_case_ids) * len(records),
            trigger_type='dataset_driven',
            environment=environment,
            status='pending',
            started_by=request.user,
            metadata={
                'dataset_id': dataset_id,
                'dataset_name': dataset.name,
                'record_count': len(records)
            }
        )
        
        try:
            # 对每条数据集记录执行一次
            all_results = []
            for idx, record in enumerate(records):
                # 将数据集字段注入全局变量
                dataset_vars = {}
                if hasattr(record, 'data_content') and record.data_content:
                    for key, value in record.data_content.items():
                        dataset_vars[key] = value
                
                # 合并套件全局变量和数据集变量
                global_vars = {}
                if suite.suite_vars and 'global_vars' in suite.suite_vars:
                    for var in suite.suite_vars['global_vars']:
                        if var.get('name') and var.get('value'):
                            global_vars[var['name']] = var['value']
                
                global_vars.update(dataset_vars)
                
                # 创建子执行记录
                sub_execution = TestExecution.objects.create(
                    name=f'{execution_name} - 批次 {idx + 1}/{len(records)}',
                    parent_execution=execution,
                    test_suite=suite,
                    test_cases=suite.test_cases,
                    web_test_cases=suite.web_test_cases,
                    total_count=len(all_case_ids),
                    trigger_type='dataset_iteration',
                    environment=environment,
                    status='pending',
                    started_by=request.user,
                    metadata={'iteration': idx + 1, 'dataset_record_id': record.id}
                )
                
                # 执行
                engine = TestExecutionEngine(sub_execution.id, global_variables=global_vars)
                result = engine.execute()
                all_results.append(result)
            
            # 汇总结果
            total_passed = sum(r.passed_count for r in all_results)
            total_failed = sum(r.failed_count for r in all_results)
            total_skipped = sum(r.skipped_count for r in all_results)
            
            execution.status = 'completed'
            execution.passed_count = total_passed
            execution.failed_count = total_failed
            execution.skipped_count = total_skipped
            execution.completed_at = timezone.now()
            execution.save()
            
            return Response({
                'execution_id': execution.id,
                'status': execution.status,
                'total_count': execution.total_count,
                'passed_count': total_passed,
                'failed_count': total_failed,
                'skipped_count': total_skipped,
                'name': execution.name,
                'iterations': len(records)
            })
        except Exception as e:
            import traceback
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.save()
            return Response({'error': str(e), 'traceback': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            error_detail = f"{str(e)}\n\n{traceback.format_exc()}"
            execution.status = 'failed'
            execution.execution_log = error_detail
            execution.save()
            return Response({
                'error': str(e),
                'detail': error_detail
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
