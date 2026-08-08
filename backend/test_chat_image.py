import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from knowledge_base.services import RAGEngine

# 测试不带图片
try:
    r = RAGEngine()
    print("RAGEngine 初始化成功，模型:", r.llm.model_name)
    result = r.chat("你好", system_prompt=None, images=None)
    print("无图片测试成功:", result['answer'][:50])
except Exception as e:
    import traceback
    traceback.print_exc()

# 测试带图片（模拟一个小的 base64）
try:
    r = RAGEngine()
    # 用一个极小的 1x1 像素的透明 PNG base64
    tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    result = r.chat("描述这张图片", system_prompt=None, images=[tiny_png])
    print("带图片测试成功:", result['answer'][:50])
except Exception as e:
    import traceback
    traceback.print_exc()
