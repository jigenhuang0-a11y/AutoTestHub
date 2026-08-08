"""真正的 midscene 端到端测试 - 用新 API Key"""
import os, sys, json, tempfile, subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
from web_testcases.playwright_engine import _generate_midscene_script

# 生成 midscene 脚本
tmp = tempfile.mkdtemp(prefix='midscene_real_')
scr_dir = os.path.join(tmp, 'screenshots')
os.makedirs(scr_dir, exist_ok=True)
script_path = os.path.join(tmp, 'run_test.py')

script = _generate_midscene_script(
    ai_prompt='点击搜索框\n在搜索框输入hello world',
    target_url='https://www.baidu.com',
    headless=True,
    viewport={'width': 1280, 'height': 720},
    screenshot_enabled=True,
    output_dir=tmp.replace('\\', '/'),
    screenshots_dir=scr_dir.replace('\\', '/'),
)

with open(script_path, 'w', encoding='utf-8') as f:
    f.write(script)

print(f'Script: {script_path}')
print(f'Output dir: {tmp}')
print('=' * 60)
print('Running Midscene AI Web Test...')
print('Target: https://www.baidu.com')
print('Action: click search box, type "hello world"')
print('=' * 60)

result = subprocess.run(
    [sys.executable, '-u', script_path],
    capture_output=False,
    text=True,
    timeout=180,
    cwd=tmp,
    env={**os.environ},
)

print('\n' + '=' * 60)
print('TEST COMPLETED')
print('=' * 60)

# 读取结果
result_file = os.path.join(tmp, 'result.json')
if os.path.exists(result_file):
    with open(result_file, 'r', encoding='utf-8') as f:
        r = json.load(f)
    print(f'\nStatus: {r.get("status")}')
    print(f'Total time: {r.get("total_time")}s')
    steps = r.get('steps_results', [])
    print(f'Steps completed: {len(steps)}/{len(steps)}')
    for s in steps:
        print(f'  - Step {s.get("step")}: {s.get("status")} - {s.get("instruction", "")[:50]}')
    if r.get('error'):
        print(f'\nError: {r["error"]}')
else:
    print('\nNo result.json found')
    files = os.listdir(tmp)
    print(f'Files: {files}')
