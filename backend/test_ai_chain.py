"""最小化测试：只验证 midscene AI 调用链（不开浏览器）"""
import os, sys, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from midscene.core.ai_model import AIModelConfig
from midscene.core.ai_model.service import AIModelService
from midscene.core.insight import LocateResponse  # insight 里定义的结构化响应

async def main():
    model_config = AIModelConfig(
        provider='openai',
        model='qwen-vl-max',
        api_key=os.getenv('MIDSCENE_AI_API_KEY'),
        base_url=os.getenv('MIDSCENE_AI_BASE_URL'),
        max_tokens=4000,
        temperature=0.1,
    )
    
    ai_service = AIModelService()

    # Test 1: 简单文本调用
    print("=== Test 1: 纯文本调用 ===")
    result = await ai_service.call_ai(
        messages=[{"role": "user", "content": "回复 OK"}],
        model_config=model_config,
    )
    print(f"Success: {result is not None}")
    print(f"Content type: {type(result.get('content')).__name__}")
    print(f"Content: {str(result.get('content', ''))[:200]}")
    print()

    # Test 2: 带结构化 schema 调用 (这是 insight.locate 会做的)
    print("=== Test 2: 带 LocateResponse schema 调用 ===")
    print(f"LocateResponse fields: {list(LocateResponse.model_fields.keys())}")
    try:
        result2 = await ai_service.call_ai(
            messages=[
                {"role": "system", "content": "你是UI分析助手。返回JSON。"},
                {"role": "user", "content": '返回 {"x":100,"y":200,"element_id":"btn1","confidence":0.9}'}
            ],
            response_schema=LocateResponse,
            model_config=model_config,
        )
        print(f"Success!")
        print(f"Content: {json.dumps(result2.get('content'), ensure_ascii=False, indent=2)[:500]}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

import asyncio
asyncio.run(main())
