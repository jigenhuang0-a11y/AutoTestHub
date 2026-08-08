import os, sys, json, tempfile
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
import django; django.setup()
from web_testcases.playwright_engine import _generate_midscene_script

script = _generate_midscene_script(
    ai_prompt='打开豆包页面',
    target_url='https://www.doubao.com',
    headless=True,
    viewport={'width':1280,'height':720},
    screenshot_enabled=True,
    output_dir=tempfile.mkdtemp(),
    screenshots_dir=tempfile.mkdtemp()
)

# Show only the config lines (first 50 lines)
lines = script.split('\n')
for i, line in enumerate(lines[:50], 1):
    # Mask most of the api_key
    masked = line
    if 'API_KEY' in line and 'sk-' in line:
        idx = line.index('sk-')
        end = idx + min(len(line) - idx, 20)
        masked = line[:idx] + line[idx:end] + '...' + line[-3:]
    print(f'{i:4}: {masked}')
