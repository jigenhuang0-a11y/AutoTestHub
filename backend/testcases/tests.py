"""
测试用例模块 - 单元测试
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import TestCase as TestCaseModel

User = get_user_model()


class TestCaseModelTest(TestCase):
    """测试用例模型层测试"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )

    def test_create_test_case(self):
        """测试创建用例"""
        tc = TestCaseModel.objects.create(
            title='测试登录接口',
            description='验证登录接口的正常流程',
            api_endpoint='/api/login',
            method='POST',
            headers={'Content-Type': 'application/json'},
            request_body={'username': 'admin', 'password': '123456'},
            expected_status_code=200,
            expected_response={'code': 0, 'msg': 'success'},
            assertion_rules=[
                {'field': 'code', 'operator': 'eq', 'value': 0}
            ],
            priority='P0',
            status='active',
            created_by=self.user,
        )
        self.assertEqual(tc.title, '测试登录接口')
        self.assertEqual(tc.method, 'POST')
        self.assertEqual(tc.priority, 'P0')
        self.assertEqual(tc.status, 'active')
        self.assertEqual(str(tc), '测试登录接口')

    def test_default_values(self):
        """测试默认值"""
        tc = TestCaseModel.objects.create(
            title='默认值测试用例',
            created_by=self.user,
        )
        self.assertEqual(tc.method, 'GET')
        self.assertEqual(tc.expected_status_code, 200)
        self.assertEqual(tc.priority, 'P2')
        self.assertEqual(tc.status, 'draft')
        self.assertEqual(tc.headers, {})
        self.assertEqual(tc.request_body, {})
        self.assertEqual(tc.expected_response, {})
        self.assertEqual(tc.assertion_rules, [])
        self.assertEqual(tc.extract_rules, [])
        self.assertEqual(tc.global_vars, [])
        self.assertEqual(tc.context_vars, [])

    def test_priority_choices(self):
        """测试优先级选项"""
        tc = TestCaseModel.objects.create(
            title='P3用例', priority='P3', created_by=self.user
        )
        self.assertEqual(tc.get_priority_display(), 'P3 - 低')

    def test_status_choices(self):
        """测试状态流转"""
        tc = TestCaseModel.objects.create(
            title='草稿用例', status='draft', created_by=self.user
        )
        self.assertEqual(tc.get_status_display(), '草稿')

        tc.status = 'active'
        tc.save()
        tc.refresh_from_db()
        self.assertEqual(tc.status, 'active')

        tc.status = 'inactive'
        tc.save()
        tc.refresh_from_db()
        self.assertEqual(tc.status, 'inactive')

    def test_ordering(self):
        """测试排序（按创建时间倒序）"""
        import time
        tc1 = TestCaseModel.objects.create(
            title='旧用例', created_by=self.user
        )
        time.sleep(0.01)  # 确保时间戳不同
        tc2 = TestCaseModel.objects.create(
            title='新用例', created_by=self.user
        )
        cases = list(TestCaseModel.objects.all())
        self.assertEqual(cases[0].title, '新用例')
        self.assertEqual(cases[1].title, '旧用例')

    def test_extract_rules_json(self):
        """测试JSON字段存储与读取"""
        rules = [
            {'source': 'response', 'field': 'token', 'var': 'auth_token'},
            {'source': 'response', 'field': 'user_id', 'var': 'uid'},
        ]
        tc = TestCaseModel.objects.create(
            title='提取规则测试',
            extract_rules=rules,
            created_by=self.user,
        )
        tc.refresh_from_db()
        self.assertEqual(len(tc.extract_rules), 2)
        self.assertEqual(tc.extract_rules[0]['var'], 'auth_token')


class TestCaseAPITest(TestCase):
    """测试用例 API 层测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='apiuser', password='apipass123'
        )
        # 获取JWT token
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'apiuser',
            'password': 'apipass123',
        })
        self.token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        # 创建测试数据
        self.tc = TestCaseModel.objects.create(
            title='API测试用例',
            api_endpoint='/api/test',
            method='GET',
            priority='P1',
            status='active',
            created_by=self.user,
        )

    def test_list_testcases(self):
        """测试获取用例列表"""
        response = self.client.get(reverse('testcase-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_create_testcase_api(self):
        """测试通过API创建用例"""
        data = {
            'title': 'API创建测试',
            'api_endpoint': '/api/user/info',
            'method': 'GET',
            'priority': 'P0',
            'status': 'draft',
        }
        response = self.client.post(reverse('testcase-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'API创建测试')

    def test_get_testcase_detail(self):
        """测试获取用例详情"""
        response = self.client.get(
            reverse('testcase-detail', kwargs={'pk': self.tc.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'API测试用例')

    def test_update_testcase(self):
        """测试更新用例"""
        data = {'title': '更新后的用例', 'priority': 'P0'}
        response = self.client.patch(
            reverse('testcase-detail', kwargs={'pk': self.tc.pk}),
            data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], '更新后的用例')
        self.assertEqual(response.data['priority'], 'P0')

    def test_delete_testcase(self):
        """测试删除用例"""
        tc = TestCaseModel.objects.create(
            title='待删除用例', created_by=self.user
        )
        response = self.client.delete(
            reverse('testcase-detail', kwargs={'pk': tc.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TestCaseModel.objects.filter(pk=tc.pk).exists())

    def test_unauthenticated_access(self):
        """测试未认证访问被拒绝"""
        unauth_client = APIClient()
        response = unauth_client.get(reverse('testcase-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_priority(self):
        """测试按优先级筛选"""
        TestCaseModel.objects.create(
            title='P0用例', priority='P0', created_by=self.user
        )
        TestCaseModel.objects.create(
            title='P3用例', priority='P3', created_by=self.user
        )
        response = self.client.get(
            reverse('testcase-list'), {'priority': 'P0'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data['results']:
            self.assertEqual(item['priority'], 'P0')

    def test_search_testcase(self):
        """测试搜索用例"""
        response = self.client.get(
            reverse('testcase-list'), {'search': 'API测试'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)


class TestCaseIntegrationTest(TestCase):
    """测试用例集成测试 - 完整CRUD流程"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='integuser', password='integpass123'
        )
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'integuser',
            'password': 'integpass123',
        })
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}'
        )

    def test_full_crud_flow(self):
        """完整CRUD流程测试"""
        # 1. 创建
        create_data = {
            'title': '集成测试-用户注册',
            'description': '测试用户注册接口全流程',
            'api_endpoint': '/api/register',
            'method': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'request_body': {
                'username': 'newuser',
                'password': 'Pass123!',
                'email': 'test@example.com',
            },
            'expected_status_code': 201,
            'assertion_rules': [
                {'field': 'code', 'operator': 'eq', 'value': 0},
                {'field': 'data.user_id', 'operator': 'exists', 'value': True},
            ],
            'priority': 'P0',
            'status': 'draft',
        }
        create_resp = self.client.post(
            reverse('testcase-list'), create_data, format='json'
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        tc_id = create_resp.data['id']

        # 2. 读取
        get_resp = self.client.get(
            reverse('testcase-detail', kwargs={'pk': tc_id})
        )
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data['method'], 'POST')

        # 3. 更新
        update_data = {
            'status': 'active',
            'description': '更新后的描述-增加异常场景',
        }
        update_resp = self.client.patch(
            reverse('testcase-detail', kwargs={'pk': tc_id}),
            update_data, format='json'
        )
        self.assertEqual(update_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(update_resp.data['status'], 'active')

        # 4. 验证列表中存在
        list_resp = self.client.get(reverse('testcase-list'))
        ids = [item['id'] for item in list_resp.data['results']]
        self.assertIn(tc_id, ids)

        # 5. 删除
        del_resp = self.client.delete(
            reverse('testcase-detail', kwargs={'pk': tc_id})
        )
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

        # 6. 验证已删除
        get_after_del = self.client.get(
            reverse('testcase-detail', kwargs={'pk': tc_id})
        )
        self.assertEqual(get_after_del.status_code, status.HTTP_404_NOT_FOUND)
