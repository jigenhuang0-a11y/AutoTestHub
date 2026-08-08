"""
初始化 AI 模型配置 - 将预配置的模型信息写入数据库
用法: python seed_model_configs.py
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from ai_evaluator.models import AIModelConfig

# ============================================================
# 预定义模型配置
# ============================================================
DEFAULT_MODELS = [
    {
        'name': 'DeepSeek Chat',
        'provider': 'deepseek',
        'model_id': 'deepseek-chat',
        'api_url': 'https://api.deepseek.com/v1/chat/completions',
        'api_key': os.getenv('DEEPSEEK_API_KEY', ''),
        'description': 'DeepSeek V3 大模型，擅长代码生成、逻辑推理与技术问答',
        'timeout': 120,
        'max_tokens': 8192,
        'temperature': 0.3,
        'is_active': True,
    },
    {
        'name': '通义千问 Max',
        'provider': 'qwen',
        'model_id': 'qwen-max',
        'api_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        'api_key': os.getenv('DASHSCOPE_API_KEY', ''),
        'description': '通义千问最强模型，擅长复杂推理、评估与规划',
        'timeout': 120,
        'max_tokens': 8192,
        'temperature': 0.3,
        'is_active': True,
    },
    {
        'name': '通义千问 Plus',
        'provider': 'qwen',
        'model_id': 'qwen-plus',
        'api_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        'api_key': os.getenv('DASHSCOPE_API_KEY', ''),
        'description': '通义千问 Plus 版本，平衡性能与成本，适合日常任务',
        'timeout': 60,
        'max_tokens': 4096,
        'temperature': 0.5,
        'is_active': True,
    },
    {
        'name': '通义千问 Turbo',
        'provider': 'qwen',
        'model_id': 'qwen-turbo',
        'api_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        'api_key': os.getenv('DASHSCOPE_API_KEY', ''),
        'description': '通义千问轻量版，快速响应，适合简单对话和降级兜底',
        'timeout': 30,
        'max_tokens': 2048,
        'temperature': 0.7,
        'is_active': True,
    },
]


def seed():
    created = 0
    updated = 0
    skipped = 0

    for cfg in DEFAULT_MODELS:
        # 用 (provider, model_id) 作为唯一标识，避免重复创建
        obj, is_new = AIModelConfig.objects.update_or_create(
            provider=cfg['provider'],
            model_id=cfg['model_id'],
            defaults={
                'name': cfg['name'],
                'api_url': cfg['api_url'],
                'api_key': cfg['api_key'],
                'description': cfg['description'],
                'timeout': cfg['timeout'],
                'max_tokens': cfg['max_tokens'],
                'temperature': cfg['temperature'],
                'is_active': cfg['is_active'],
            }
        )
        if is_new:
            print(f'  [NEW] {cfg["name"]} ({cfg["provider"]}/{cfg["model_id"]})')
            created += 1
        else:
            print(f'  [EXIST] {cfg["name"]} ({cfg["provider"]}/{cfg["model_id"]})')
            updated += 1

    print(f'\nDone: {created} created, {updated} updated, {skipped} skipped')
    print(f'Total models in DB: {AIModelConfig.objects.count()}')


if __name__ == '__main__':
    seed()
