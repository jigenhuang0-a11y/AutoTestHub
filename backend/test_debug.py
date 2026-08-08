import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_test_platform.settings'
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first()
print(f"User: {user.username if user else 'None'}")

c = APIClient()
c.force_authenticate(user=user)

# 测试 ID=6 的用例 (GET http://localhost:10011/hello)
print("\n=== Testing debug for case ID=6 ===")
resp = c.post('/api/testcases/6/debug/', {'global_variables': {}}, format='json')
print(f"Status: {resp.status_code}")
print(f"Data: {resp.data}")

# 也测试 ID=12
print("\n=== Testing debug for case ID=12 ===")
resp = c.post('/api/testcases/12/debug/', {'global_variables': {}}, format='json')
print(f"Status: {resp.status_code}")
print(f"Data: {resp.data}")
