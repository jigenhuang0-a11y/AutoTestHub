"""
测试执行模块 - 单元测试
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import TestExecution

User = get_user_model()


class TestExecutionModelTest(TestCase):
    """执行记录模型层测试"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='execuser', password='execpass123'
        )

    def test_create_execution(self):
        """测试创建执行记录"""
        execution = TestExecution.objects.create(
            name='登录接口回归测试',
            test_cases=[1, 2, 3, 4, 5],
            status='pending',
            trigger_type='manual_case',
            environment='test',
            total_count=5,
            started_by=self.user,
        )
        self.assertEqual(execution.name, '登录接口回归测试')
        self.assertEqual(execution.total_count, 5)
        self.assertEqual(execution.status, 'pending')
        self.assertEqual(execution.trigger_type, 'manual_case')
        self.assertEqual(execution.environment, 'test')

    def test_default_values(self):
        """测试默认值"""
        execution = TestExecution.objects.create(
            test_cases=[1, 2],
            started_by=self.user,
        )
        self.assertEqual(execution.status, 'pending')
        self.assertEqual(execution.trigger_type, 'manual_suite')
        self.assertEqual(execution.environment, 'dev')
        self.assertEqual(execution.total_count, 0)
        self.assertEqual(execution.passed_count, 0)
        self.assertEqual(execution.failed_count, 0)
        self.assertEqual(execution.skipped_count, 0)
        self.assertEqual(execution.duration, 0)

    def test_status_transitions(self):
        """测试状态流转"""
        execution = TestExecution.objects.create(
            name='状态流转测试',
            test_cases=[1],
            started_by=self.user,
        )
        # pending -> running
        execution.status = 'running'
        execution.save()
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'running')

        # running -> completed
        execution.status = 'completed'
        execution.passed_count = 1
        execution.duration = 120
        execution.save()
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.passed_count, 1)
        self.assertEqual(execution.duration, 120)

    def test_trigger_types(self):
        """测试所有触发方式"""
        for trigger_type, _ in TestExecution.TRIGGER_CHOICES:
            execution = TestExecution.objects.create(
                name=f'{trigger_type}触发',
                test_cases=[1],
                trigger_type=trigger_type,
                started_by=self.user,
            )
            self.assertEqual(execution.trigger_type, trigger_type)

    def test_environment_choices(self):
        """测试环境选项"""
        environments = ['dev', 'test', 'prod']
        for env in environments:
            execution = TestExecution.objects.create(
                name=f'{env}环境执行',
                test_cases=[1],
                environment=env,
                started_by=self.user,
            )
            self.assertEqual(execution.environment, env)

    def test_execution_results_json(self):
        """测试执行结果JSON存储"""
        results = [
            {
                'case_id': 1,
                'title': '测试用例1',
                'status': 'passed',
                'duration': 1.5,
            },
            {
                'case_id': 2,
                'title': '测试用例2',
                'status': 'failed',
                'error': 'AssertionError: expected 200 got 500',
                'duration': 2.1,
            },
        ]
        execution = TestExecution.objects.create(
            name='JSON结果测试',
            test_cases=[1, 2],
            total_count=2,
            passed_count=1,
            failed_count=1,
            execution_results=results,
            started_by=self.user,
        )
        execution.refresh_from_db()
        self.assertEqual(len(execution.execution_results), 2)
        self.assertEqual(execution.execution_results[0]['status'], 'passed')
        self.assertEqual(execution.execution_results[1]['status'], 'failed')

    def test_str_representation(self):
        """测试字符串表示"""
        e1 = TestExecution.objects.create(
            name='有名称的执行', test_cases=[1], started_by=self.user
        )
        self.assertEqual(str(e1), '有名称的执行')

        e2 = TestExecution.objects.create(
            test_cases=[1], started_by=self.user
        )
        self.assertIn('执行 #', str(e2))

    def test_ordering(self):
        """测试排序（按开始时间倒序）"""
        e1 = TestExecution.objects.create(
            name='旧执行', test_cases=[1], started_by=self.user
        )
        e2 = TestExecution.objects.create(
            name='新执行', test_cases=[1], started_by=self.user
        )
        executions = list(TestExecution.objects.all())
        self.assertEqual(executions[0].name, '新执行')
        self.assertEqual(executions[1].name, '旧执行')

    def test_completed_at(self):
        """测试完成时间"""
        from django.utils import timezone
        execution = TestExecution.objects.create(
            name='完成时间测试',
            test_cases=[1],
            status='completed',
            started_by=self.user,
        )
        execution.completed_at = timezone.now()
        execution.save()
        execution.refresh_from_db()
        self.assertIsNotNone(execution.completed_at)

    def test_statistics_consistency(self):
        """测试统计一致性"""
        execution = TestExecution.objects.create(
            name='统计测试',
            test_cases=[1, 2, 3, 4, 5],
            total_count=5,
            passed_count=3,
            failed_count=1,
            skipped_count=1,
            started_by=self.user,
        )
        self.assertEqual(
            execution.passed_count + execution.failed_count + execution.skipped_count,
            execution.total_count,
        )


class TestExecutionEdgeCaseTest(TestCase):
    """执行记录边界情况测试"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='edgeuser', password='edgepass123'
        )

    def test_empty_test_cases(self):
        """测试空用例列表"""
        execution = TestExecution.objects.create(
            name='空用例执行',
            test_cases=[],
            started_by=self.user,
        )
        self.assertEqual(execution.test_cases, [])
        self.assertEqual(execution.total_count, 0)

    def test_large_test_cases(self):
        """测试大量用例"""
        case_ids = list(range(1, 101))  # 100个用例
        execution = TestExecution.objects.create(
            name='大批量执行',
            test_cases=case_ids,
            total_count=100,
            started_by=self.user,
        )
        self.assertEqual(len(execution.test_cases), 100)
        self.assertEqual(execution.total_count, 100)

    def test_allure_report_path(self):
        """测试Allure报告路径"""
        execution = TestExecution.objects.create(
            name='带报告的执行',
            test_cases=[1],
            allure_report_path='/reports/exec_42/index.html',
            started_by=self.user,
        )
        self.assertIn('exec_42', execution.allure_report_path)
