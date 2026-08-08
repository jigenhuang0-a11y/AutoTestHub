"""真正跑一次 midscene 测试——验证 AI 模式是否可用"""
import os, sys, json, tempfile, subprocess
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, '.')
from web_testcases.playwright_engine import _generate_midscene_script

# 生成脚本
tmp = tempfile.mkdtemp()
scr_dir = os.path.join(tmp, 'screenshots')
os.makedirs(scr_dir, exist_ok=True)
script_path = os.path.join(tmp, 'midscene_test.py')

script = _generate_midscene_script(
    ai_prompt='在搜索框输入hello world',
    target_url='https://www.baidu.com',
    headless=True,
    viewport={'width': 1280, 'height': 720},
    screenshot_enabled=True,
    output_dir=tmp.replace('\\', '/'),
    screenshots_dir=scr_dir.replace('\\', '/'),
)

with open(script_path, 'w', encoding='utf-8') as f:
    f.write(script)

print(f'Script saved to: {script_path}')
print(f'Running midscene test...')
print('=' * 60)

result = subprocess.run(
    [sys.executable, script_path],
    capture_output=True,
    text=True,
    timeout=120,
    cwd=tmp,
    env={**os.environ},
)

print('STDOUT:')
stdout = result.stdout
print(stdout[-3000:] if len(stdout) > 3000 else stdout or '(empty)')

if result.stderr:
    print('STDERR:')
    stderr = result.stderr
    print(stderr[-2000:] if len(stderr) > 2000 else stderr)

# 检查结果
result_file = os.path.join(tmp, 'result.json')
if os.path.exists(result_file):
    with open(result_file, 'r', encoding='utf-8') as f:
        r = json.load(f)
    print('=' * 60)
    status = r.get('status')
    print(f'RESULT: status={status}')
    print(f'steps_results: {json.dumps(r.get("steps_results", []), ensure_ascii=False, indent=2)}')
    err = r.get('error')
    if err:
        print(f'ERROR: {err}')
else:
    print('=' * 60)
    print(f'RESULT: result.json NOT FOUND (exit_code={result.returncode})')
    print(f'Files in {tmp}:', os.listdir(tmp))
