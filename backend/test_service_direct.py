import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from testcases.services import AITestCaseGenerator

api_doc = """接口文档：POST /api/user/register
功能：用户注册
请求参数：
  - username (string, 必填)
  - password (string, 必填)
  - email (string, 必填)
响应：
  - 200 OK 返回用户信息
  - 400 参数错误
"""

gen = AITestCaseGenerator()
print(f"Provider: {gen.provider_name}, Model: {gen.model}")

cases = gen.generate_test_cases(api_doc)
print(f"\n生成成功，共 {len(cases)} 条用例")
print("\n第一条用例：")
import json
print(json.dumps(cases[0], ensure_ascii=False, indent=2))
