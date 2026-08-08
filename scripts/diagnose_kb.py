"""诊断知识库状态"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from django.contrib.auth import get_user_model
from knowledge_base.models import KnowledgeBase

User = get_user_model()

# 检查用户
u = User.objects.get(username='admin')
print(f'User: {u.username}, id={u.id}, role={u.role}')

# 检查所有知识库
kbs = KnowledgeBase.objects.all()
print(f'\nTotal KBs: {kbs.count()}')
for kb in kbs:
    print(f'  KB id={kb.id}, name={kb.name}, created_by={kb.created_by.username}')

# 检查 ID=4 的知识库
try:
    kb4 = KnowledgeBase.objects.get(id=4)
    print(f'\nKB 4 exists: {kb4.name}, created_by={kb4.created_by.username}')
except KnowledgeBase.DoesNotExist:
    print('\nKB 4 does NOT exist!')
    # 创建它
    kb4 = KnowledgeBase.objects.create(
        id=4,
        name='测试知识库',
        description='AI 测试平台演示知识库',
        created_by=u
    )
    print(f'Created KB 4: {kb4.name}')
