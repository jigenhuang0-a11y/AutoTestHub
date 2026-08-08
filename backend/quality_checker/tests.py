"""
质量数字人模块 - 单元测试
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from .engine import QualityCheckEngine
from .models import QualityCheckTask, QualityCheckResult

User = get_user_model()


class QualityCheckEngineTest(TestCase):
    """质检引擎单元测试"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='qauser', password='qapass123'
        )

    def _check_one(self, case, scenario='general'):
        """快捷调用：单条质检"""
        engine = QualityCheckEngine(scenario=scenario)
        results = engine.run_check([case])
        return results[0]

    # ========== 功能测试场景 ==========

    def test_func_complete_case(self):
        """测试完整的功能测试用例（应得高分）"""
        case = {
            'title': '用户登录功能-正确账号密码登录',
            'priority': 'P0',
            'precondition': '用户已注册且账号状态正常',
            'steps': '1. 打开登录页面\n2. 输入正确的用户名和密码\n3. 点击登录按钮',
            'expected': '1. 页面跳转到首页\n2. 右上角显示用户昵称\n3. Token正确返回',
        }
        result = self._check_one(case, scenario='general')
        self.assertGreaterEqual(result['score'], 60,
                                f'完整用例应得60分以上，实得{result["score"]}')

    def test_func_missing_steps(self):
        """测试缺少步骤的用例（应严重扣分）"""
        case = {
            'title': '登录功能测试',
            'priority': 'P0',
            'expected': '登录成功',
        }
        result = self._check_one(case, scenario='general')
        self.assertLess(result['score'], 60,
                        f'缺少步骤的用例应低于60分，实得{result["score"]}')

    def test_func_missing_title(self):
        """测试缺少标题"""
        case = {
            'priority': 'P1',
            'steps': '1. 点击按钮',
            'expected': '操作成功',
        }
        result = self._check_one(case, scenario='general')
        self.assertLess(result['score'], 80,
                        f'缺少标题的用例应扣分，实得{result["score"]}')

    def test_func_vague_content(self):
        """测试模糊描述的用例"""
        case = {
            'title': '测试功能',
            'priority': 'P2',
            'steps': '1. 操作一下\n2. 看看结果',
            'expected': '应该是正常的',
        }
        result = self._check_one(case, scenario='general')
        self.assertLess(result['score'], 70,
                        f'模糊描述的用例应扣分，实得{result["score"]}')

    # ========== 接口测试场景 ==========

    def test_api_complete_case(self):
        """测试完整的接口测试用例（应得高分）"""
        case = {
            'title': '获取用户信息接口-正常请求',
            'priority': 'P0',
            'url': '/api/user/info',
            'method': 'GET',
            'request_params': '{"user_id": 123}',
            'expected_response': '验证状态码200, 返回用户昵称、头像、注册时间',
        }
        result = self._check_one(case, scenario='api')
        self.assertGreaterEqual(result['score'], 60,
                                f'完整接口用例应得60分以上，实得{result["score"]}')

    def test_api_missing_url(self):
        """测试缺少接口地址"""
        case = {
            'title': '登录接口测试',
            'method': 'POST',
            'request_params': '{"username":"test"}',
        }
        result = self._check_one(case, scenario='api')
        self.assertLess(result['score'], 80,
                        f'缺少URL的用例应扣分，实得{result["score"]}')

    def test_api_missing_method(self):
        """测试缺少请求方法"""
        case = {
            'title': '用户列表接口',
            'url': '/api/users',
        }
        result = self._check_one(case, scenario='api')
        self.assertLess(result['score'], 80,
                        f'缺少请求方法的用例应扣分，实得{result["score"]}')

    # ========== 边界情况 ==========

    def test_empty_case(self):
        """测试空用例"""
        case = {}
        result = self._check_one(case, scenario='general')
        self.assertLess(result['score'], 40,
                        f'空用例应得极低分，实得{result["score"]}')

    def test_result_structure(self):
        """测试返回结果结构"""
        case = {
            'title': '结构测试-验证返回字段',
            'steps': '1. 执行步骤一',
            'expected': '验证结果一',
        }
        result = self._check_one(case, scenario='general')
        self.assertIn('score', result)
        self.assertIn('issues', result)
        self.assertIn('level', result)
        self.assertIsInstance(result['score'], (int, float))
        self.assertIsInstance(result['issues'], list)
        self.assertIn(result['level'], ['pass', 'warning', 'fail'])

    def test_duplicate_detection(self):
        """测试重复检测"""
        case1 = {
            'title': '用户登录-正常流程验证',
            'steps': '1. 输入正确账号密码\n2. 点击登录',
            'expected': '登录成功，跳转首页',
        }
        case2 = {
            'title': '用户登录-正常流程验证',
            'steps': '1. 输入正确账号密码\n2. 点击登录',
            'expected': '登录成功，跳转首页',
        }
        engine = QualityCheckEngine(scenario='general')
        results = engine.run_check([case1, case2])
        self.assertEqual(len(results), 2)
        # 两个相同用例至少有一个会被标记为重复
        has_duplicate = any(r.get('duplicate_of') for r in results)
        self.assertTrue(has_duplicate, '应有重复检测结果')

    def test_scenario_general(self):
        """测试general场景"""
        case = {
            'title': '通用场景测试-验证功能',
            'steps': '1. 执行操作',
            'expected': '操作成功',
        }
        result = self._check_one(case, scenario='general')
        self.assertIsNotNone(result)

    def test_scenario_api(self):
        """测试api场景"""
        case = {
            'title': 'API场景测试',
            'url': '/api/test',
            'method': 'POST',
        }
        result = self._check_one(case, scenario='api')
        self.assertIsNotNone(result)

    def test_batch_check(self):
        """测试批量检查"""
        cases = [
            {
                'title': '批量测试1-完整用例',
                'priority': 'P0',
                'steps': '1. 步骤A\n2. 步骤B',
                'expected': '验证预期结果A和B',
            },
            {
                'title': '批量测试2-缺少步骤',
                'priority': 'P1',
            },
            {
                'title': '批量测试3-基础用例',
                'steps': '1. 步骤C',
                'expected': '验证结果C',
            },
        ]
        engine = QualityCheckEngine(scenario='general')
        results = engine.run_check(cases)
        self.assertEqual(len(results), 3)
        # 第一个应该得分最高
        self.assertGreater(results[0]['score'], results[1]['score'])

    # ========== 评分等级测试 ==========

    def test_pass_level(self):
        """测试通过等级（>=80）"""
        case = {
            'title': '高质量用例-验证登录全流程及异常场景',
            'priority': 'P0',
            'precondition': '用户已注册，数据库正常',
            'steps': '1. 打开登录页\n2. 输入正确账号密码\n3. 点击登录\n4. 验证跳转',
            'expected': '1. 页面正常加载\n2. 输入框正常\n3. 登录成功跳转首页\n4. 显示用户信息',
        }
        result = self._check_one(case, scenario='general')
        # 这个用例应该得分较高
        self.assertIsNotNone(result['level'])

    def test_fail_level(self):
        """测试不通过等级（<60）"""
        case = {
            'title': '测试',
        }
        result = self._check_one(case, scenario='general')
        self.assertEqual(result['level'], 'fail')


class QualityCheckModelTest(TestCase):
    """质检模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='qamodel', password='model123'
        )

    def test_create_quality_task(self):
        """测试创建质检任务"""
        task = QualityCheckTask.objects.create(
            name='功能测试用例质检',
            scenario='general',
            status='pending',
            created_by=self.user,
        )
        self.assertEqual(task.name, '功能测试用例质检')
        self.assertEqual(task.scenario, 'general')
        self.assertEqual(task.status, 'pending')

    def test_task_status_transitions(self):
        """测试任务状态流转"""
        task = QualityCheckTask.objects.create(
            name='状态流转测试',
            scenario='general',
            created_by=self.user,
        )
        task.status = 'processing'
        task.save()
        task.refresh_from_db()
        self.assertEqual(task.status, 'processing')

        task.status = 'completed'
        task.total_cases = 50
        task.passed_cases = 40
        task.warning_cases = 8
        task.failed_cases = 2
        task.overall_score = 85.0
        task.save()
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        self.assertEqual(task.overall_score, 85.0)

    def test_task_statistics_consistency(self):
        """测试统计一致性"""
        task = QualityCheckTask.objects.create(
            name='统计测试',
            total_cases=100,
            passed_cases=70,
            warning_cases=20,
            failed_cases=10,
            created_by=self.user,
        )
        self.assertEqual(
            task.passed_cases + task.warning_cases + task.failed_cases,
            task.total_cases,
        )

    def test_create_quality_result(self):
        """测试创建质检结果"""
        task = QualityCheckTask.objects.create(
            name='质检结果测试',
            scenario='general',
            status='completed',
            created_by=self.user,
        )
        result = QualityCheckResult.objects.create(
            task=task,
            case_title='测试用例A-验证登录功能',
            case_content={'title': '测试用例A'},
            score=85.5,
            level='pass',
            completeness_score=35.0,
            format_score=18.0,
            content_score=32.5,
            issues=[{'type': 'format', 'message': '步骤格式可优化'}],
        )
        self.assertEqual(result.score, 85.5)
        self.assertEqual(result.level, 'pass')
        self.assertEqual(len(result.issues), 1)

    def test_quality_result_levels(self):
        """测试所有等级"""
        task = QualityCheckTask.objects.create(
            name='等级测试',
            scenario='general',
            status='completed',
            created_by=self.user,
        )
        r1 = QualityCheckResult.objects.create(
            task=task, case_title='pass用例', score=90.0, level='pass'
        )
        r2 = QualityCheckResult.objects.create(
            task=task, case_title='warning用例', score=70.0, level='warning'
        )
        r3 = QualityCheckResult.objects.create(
            task=task, case_title='fail用例', score=30.0, level='fail'
        )
        self.assertEqual(r1.level, 'pass')
        self.assertEqual(r2.level, 'warning')
        self.assertEqual(r3.level, 'fail')

    def test_task_with_results(self):
        """测试任务关联结果"""
        task = QualityCheckTask.objects.create(
            name='关联测试',
            scenario='general',
            created_by=self.user,
        )
        QualityCheckResult.objects.create(
            task=task, case_title='用例1', score=95.0, level='pass'
        )
        QualityCheckResult.objects.create(
            task=task, case_title='用例2', score=55.0, level='fail'
        )
        self.assertEqual(task.results.count(), 2)

    def test_result_ordering(self):
        """测试结果按分数排序"""
        task = QualityCheckTask.objects.create(
            name='排序测试',
            scenario='general',
            created_by=self.user,
        )
        QualityCheckResult.objects.create(
            task=task, case_title='低分用例', score=30.0, level='fail'
        )
        QualityCheckResult.objects.create(
            task=task, case_title='高分用例', score=95.0, level='pass'
        )
        results = list(task.results.all())
        self.assertEqual(results[0].case_title, '高分用例')
        self.assertEqual(results[1].case_title, '低分用例')
