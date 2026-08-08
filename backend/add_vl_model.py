"""添加 qwen3-vl-flash 视觉模型到数据库"""
import os, sys, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from ai_evaluator.models import AIModelConfig

# 先看现有模型
print("现有模型：")
for m in AIModelConfig.objects.filter(is_active=True):
    print(f"  [{m.provider}] {m.name} ({m.model_id})")

# 检查是否已存在
if AIModelConfig.objects.filter(model_id='qwen3-vl-flash').exists():
    print("\nqwen3-vl-flash 已存在，无需添加")
    sys.exit(0)

# 创建视觉模型
vl = AIModelConfig.objects.create(
    name='Qwen3-VL-Flash 视觉',
    provider='qwen',
    model_id='qwen3-vl-flash',
    api_url='https://ws-uxmtm7xrs503cof5.cn-beijing.maas.aliyuncs.com/compatible-mode/v1',
    api_key='YOUR_DASHSCOPE_API_KEY',
    description='视觉语言模型，用于自动化测试的截图智能评估（阿里云百炼）',
    timeout=30,
    max_tokens=1024,
    temperature=0.1,
    is_active=True,
)

print(f"\n[OK] Added: {vl.name} ({vl.model_id})")
print(f"     URL: {vl.api_url}")

# 验证
print("\n当前全部启用模型：")
for m in AIModelConfig.objects.filter(is_active=True):
    print(f"  [{m.provider}] {m.name} ({m.model_id})")
