"""
数据库修复脚本：清理测试用例表中的无效JSON字段
运行方式: python fix_json_fields.py
"""
import os
import sys
import django

# 设置Django环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from testcases.models import TestCase


def fix_json_fields():
    """修复测试用例表中的JSON字段"""
    print("开始修复测试用例JSON字段...")
    
    test_cases = TestCase.objects.all()
    fixed_count = 0
    
    for tc in test_cases:
        needs_update = False
        
        # 修复headers字段
        if tc.headers is None or tc.headers == 0:
            tc.headers = {}
            needs_update = True
        
        # 修复request_body字段
        if tc.request_body is None or tc.request_body == 0:
            tc.request_body = {}
            needs_update = True
        
        # 修复expected_response字段
        if tc.expected_response is None or tc.expected_response == 0:
            tc.expected_response = {}
            needs_update = True
        
        # 修复tags字段
        if tc.tags is None or tc.tags == 0:
            tc.tags = []
            needs_update = True
        
        if needs_update:
            tc.save()
            fixed_count += 1
            print(f"  修复用例 #{tc.id}: {tc.title}")
    
    print(f"\n修复完成！共修复 {fixed_count} 条记录。")


if __name__ == '__main__':
    fix_json_fields()
