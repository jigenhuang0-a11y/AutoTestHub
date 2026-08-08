"""测试 DashScope 原生 SDK 是否能通"""
import os, sys
from dotenv import load_dotenv
load_dotenv()
import dashscope

dashscope.api_key = os.getenv('DASHSCOPE_API_KEY')
print(f'API Key: {dashscope.api_key[:25]}...')

resp = dashscope.Generation.call(
    model='qwen-vl-max',
    messages=[{'role': 'user', 'content': 'say hi'}],
    max_tokens=10,
    result_format='message'
)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    content = resp.output.choices[0]['message']['content']
    print(f'Content: {content}')
else:
    print(f'Error: {resp.code} - {resp.message}')
