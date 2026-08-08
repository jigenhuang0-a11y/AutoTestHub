import os, json, sys, asyncio
from dotenv import load_dotenv
load_dotenv()
import httpx

sys.stdout.reconfigure(encoding='utf-8')
api_key = os.getenv('DASHSCOPE_API_KEY')

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(
            'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'model': 'qwen-vl-max', 'messages': [{'role': 'user', 'content': 'say OK'}], 'max_tokens': 20}
        )
        print(f'Status: {resp.status_code}')
        data = resp.json()
        if 'choices' in data:
            content = data['choices'][0]['message']['content']
            print(f'Content: {content}')
            print(f'Model: {data.get("model", "?")}')
            if 'usage' in data:
                print(f'Usage: {json.dumps(data["usage"])}')
        else:
            print(f'Error: {json.dumps(data, ensure_ascii=False)[:500]}')

asyncio.run(main())
