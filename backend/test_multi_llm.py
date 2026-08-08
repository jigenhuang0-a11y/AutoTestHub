"""
多模型 Provider 测试脚本
用法: python test_multi_llm.py
"""
import os
import sys
import io
import django

# 强制 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from core.llm_provider import LLMProviderFactory

messages = [
    {"role": "user", "content": "用一句话介绍深圳。"}
]

# ---------- 1. 千问同步 ----------
print("=" * 50)
print("[1] 千问 qwen-plus 同步调用")
print("=" * 50)
try:
    qwen = LLMProviderFactory.create('dashscope', model='qwen-plus')
    result = qwen.chat(messages)
    print(result)
    print("[OK] 千问同步通过\n")
except Exception as e:
    print(f"[FAIL] 千问: {e}\n")

# ---------- 2. 千问流式 ----------
print("=" * 50)
print("[2] 千问 qwen-plus 流式调用")
print("=" * 50)
try:
    print(">>> ", end="", flush=True)
    for chunk in qwen.chat_stream(messages):
        print(chunk, end="", flush=True)
    print("\n[OK] 千问流式通过\n")
except Exception as e:
    print(f"\n[FAIL] 千问流式: {e}\n")

# ---------- 3. Embedding ----------
print("=" * 50)
print("[3] 千问 Embedding (text-embedding-v3)")
print("=" * 50)
try:
    vec = qwen.embed("深圳是中国的科技创新中心")
    print(f"向量维度: {len(vec)}")
    print(f"前5维: {vec[:5]}")
    print("[OK] Embedding 通过\n")
except Exception as e:
    print(f"[FAIL] Embedding: {e}\n")

# ---------- 4. DeepSeek ----------
print("=" * 50)
print("[4] DeepSeek 同步调用")
print("=" * 50)
try:
    ds = LLMProviderFactory.create('deepseek', model='deepseek-chat')
    result = ds.chat(messages)
    print(result)
    print("[OK] DeepSeek 通过\n")
except Exception as e:
    print(f"[SKIP] DeepSeek暂不可用: {e}")
    print("  需要: 注册 https://platform.deepseek.com/ 获取API Key")
    print("  在 .env 中设置: DEEPSEEK_API_KEY=sk-xxx\n")

# ---------- 5. GLM ----------
print("=" * 50)
print("[5] GLM (智谱) 同步调用")
print("=" * 50)
try:
    glm = LLMProviderFactory.create('glm', model='glm-4-flash')
    result = glm.chat(messages)
    print(result)
    print("[OK] GLM 通过\n")
except Exception as e:
    print(f"[SKIP] GLM暂不可用: {e}")
    print("  需要: 注册 https://open.bigmodel.cn/ 获取API Key")
    print("  在 .env 中设置: GLM_API_KEY=xxx\n")

# ---------- 6. 工厂批量创建 ----------
print("=" * 50)
print("[6] 工厂批量创建 (create_all)")
print("=" * 50)
providers = LLMProviderFactory.create_all()
for name, p in providers.items():
    print(f"  [OK] {name}: {p}")
if len(providers) < 3:
    print(f"  [NOTE] 只有 {len(providers)}/3 个Provider可用，其余需配置API Key")

print("\n===== 测试完成 =====")
