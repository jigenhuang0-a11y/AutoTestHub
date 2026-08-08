"""用用户创建的测试用例 - 豆包询问 - 跑 midscene"""
import os, sys, json, tempfile, subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
from web_testcases.playwright_engine import _generate_midscene_script

# ========== 用户创建的测试用例: 豆包询问 ==========
AI_PROMPT = "打开豆包页面\n在输入框中输入 你好！豆包\n点击发送按钮"
TARGET_URL = "https://www.doubao.com/chat/19388764382917378"

tmp = tempfile.mkdtemp(prefix='midscene_doubao_')
scr_dir = os.path.join(tmp, 'screenshots')
os.makedirs(scr_dir, exist_ok=True)
script_path = os.path.join(tmp, 'run_test.py')

script = _generate_midscene_script(
    ai_prompt=AI_PROMPT,
    target_url=TARGET_URL,
    headless=True,
    viewport={'width': 1280, 'height': 720},
    screenshot_enabled=True,
    output_dir=tmp.replace('\\', '/'),
    screenshots_dir=scr_dir.replace('\\', '/'),
)

with open(script_path, 'w', encoding='utf-8') as f:
    f.write(script)

print(f'用例: 豆包询问')
print(f'URL: {TARGET_URL}')
print(f'Prompt:\n{AI_PROMPT}')
print(f'Script: {script_path}')
print('=' * 60)
print('Running Midscene AI Web Test...')
print('=' * 60)

result = subprocess.run(
    [sys.executable, '-u', script_path],
    text=True,
    timeout=180,
    cwd=tmp,
    env={**os.environ},
)

print('\n' + '=' * 60)
print('TEST COMPLETED')
print(f'Exit code: {result.returncode}')
print('=' * 60)

# 读取结果
result_file = os.path.join(tmp, 'result.json')
if os.path.exists(result_file):
    with open(result_file, 'r', encoding='utf-8') as f:
        r = json.load(f)
    print(f'\nStatus: {r.get("status")}')
    print(f'Total time: {r.get("total_time")}s')
    steps = r.get('steps_results', [])
    for s in steps:
        status = s.get('status', '?')
        instr = s.get('instruction', '')[:60]
        err = s.get('error', '')
        print(f'  Step {s.get("step")}: {status} | {instr}')
        if err:
            print(f'    Error: {err[:200]}')
    if r.get('error'):
        print(f'\nOverall Error: {r["error"][:300]}')
else:
    print('\nNo result.json found')
    for f in sorted(os.listdir(tmp)):
        print(f'  {f}')
