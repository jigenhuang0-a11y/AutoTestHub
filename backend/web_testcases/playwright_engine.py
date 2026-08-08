"""
Playwright 执行引擎 - Web 自动化测试的核心执行器

支持两种模式：
1. Playwright 精确模式: 按 steps 中的操作步骤逐个执行
2. AI 模式 (midscene): 通过 midscene AI 视觉驱动，自然语言直接操作页面
"""

import json
import os
import re
import tempfile
import shutil
import time
import sys
import textwrap
from pathlib import Path
from datetime import datetime

from django.conf import settings

# 导入沙箱适配器
try:
    from execution.sandbox_adapter import sandbox_run as _sandbox_run
    _USE_SANDBOX = True
except ImportError:
    import subprocess as _subprocess
    _USE_SANDBOX = False


def _get_chromium_executable_path():
    """检测系统 Chromium 可执行路径，优先使用环境变量覆盖。"""
    env = os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
    if env and os.path.exists(env):
        return env
    for name in ('chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable'):
        p = shutil.which(name)
        if p:
            return p
    return None


def run_web_test(test_case, *, user_id=None):
    """
    执行一个 Web 测试用例
    test_case 可以是数据库对象或字典/临时对象
    user_id: 用户 ID，用于持久化浏览器数据隔离（不同用户保留各自的登录状态）

    返回:
    {
        'status': 'passed' | 'failed' | 'error',
        'steps_results': [...],
        'screenshot_path': str | None,
        'video_path': str | None,
        'assertion_errors': [...],
        'error': str | None,
        'duration': float,
    }
    """
    start_time = time.time()

    def _get(attr, default=None):
        if isinstance(test_case, dict):
            return test_case.get(attr, default)
        return getattr(test_case, attr, default)

    engine = _get('engine', 'playwright')
    target_url = _get('target_url', '')
    browser_type = _get('browser_type', 'chromium')
    headless = _get('headless', True)
    viewport = _get('viewport') or {'width': 1280, 'height': 720}
    steps = _get('steps') or []
    ai_prompt = _get('ai_prompt', '')
    assertions = _get('assertions') or []
    screenshot_enabled = _get('screenshot_enabled', True)
    full_page_screenshot = _get('full_page_screenshot', False)
    record_video = _get('record_video', False)
    cookies = _get('cookies') or []

    # === 生成并执行 Playwright 脚本 ===
    results_dir = Path(tempfile.mkdtemp(prefix='web_exec_'))
    screenshots_dir = results_dir / 'screenshots'
    screenshots_dir.mkdir(exist_ok=True)

    # 持久化浏览器数据目录（用于保存 cookies/登录状态，跨执行保持登录）
    # 按 user_id 隔离，不同用户互不干扰
    _uid = user_id or _get('user_id') or 'default'
    user_id = str(_uid)
    persistent_data_base = Path(settings.BASE_DIR) / 'browser_data' / user_id
    persistent_data_base.mkdir(parents=True, exist_ok=True)
    persistent_data_dir = str(persistent_data_base)

    # === AI 模式：使用 midscene 视觉驱动，直接执行自然语言指令 ===
    if engine == 'ai' and ai_prompt:
        test_script = _generate_midscene_script(
            ai_prompt=ai_prompt,
            target_url=target_url,
            headless=headless,
            viewport=viewport,
            screenshot_enabled=screenshot_enabled,
            output_dir=str(results_dir),
            screenshots_dir=str(screenshots_dir),
            persistent_data_dir=persistent_data_dir,
            cookies=cookies,
        )
    else:
        # === Playwright 精确模式 ===
        if not steps:
            # 兼容旧 AI 模式（无 midscene）：回退到正则解析
            if ai_prompt:
                steps = _ai_prompt_to_steps(ai_prompt, target_url)
            else:
                return {
                    'status': 'error',
                    'error': '无可用执行步骤（请提供操作步骤或 AI 测试描述）',
                    'duration': round(time.time() - start_time, 3),
                    'steps_results': [],
                    'assertion_errors': ['无步骤可执行'],
                }

        test_script = _generate_playwright_script(
            target_url=target_url,
            browser_type=browser_type,
            headless=headless,
            viewport=viewport,
            steps=steps,
            assertions=assertions,
            screenshot_enabled=screenshot_enabled,
            full_page_screenshot=full_page_screenshot,
            record_video=record_video,
            output_dir=str(results_dir),
            screenshots_dir=str(screenshots_dir),
            persistent_data_dir=persistent_data_dir,
            cookies=cookies,
        )

    script_path = results_dir / 'test_script.py'
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(test_script)

    result_file = results_dir / 'result.json'

    exec_result = {
        'status': 'error',
        'steps_results': [],
        'assertion_errors': [],
        'screenshot_path': None,
        'video_path': None,
        'error': None,
        'duration': 0,
    }

    try:
        if _USE_SANDBOX:
            result = _sandbox_run(
                [sys.executable, str(script_path)],
                timeout=120,
                max_memory_mb=1024,
                cwd=str(results_dir),
            )
            # 解析结果 JSON
            if result_file.exists():
                with open(result_file, 'r', encoding='utf-8') as f:
                    exec_result.update(json.load(f))
            else:
                exec_result['status'] = 'failed'
                if result.killed_by_timeout:
                    exec_result['error'] = '执行超时(120秒)'
                elif result.killed_by_memory:
                    exec_result['error'] = f'内存超限({result.peak_memory_mb:.0f}MB)'
                else:
                    exec_result['error'] = result.stderr.strip() or ('脚本无输出' if not result.stdout.strip() else f'stdout: {result.stdout.strip()[-2000:]}')
        else:
            proc = _subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(results_dir),
            )

            # 解析结果 JSON
            if result_file.exists():
                with open(result_file, 'r', encoding='utf-8') as f:
                    exec_result.update(json.load(f))
            else:
                stderr = proc.stderr.strip()
                stdout = proc.stdout.strip()[-2000:]
                exec_result['status'] = 'failed'
                exec_result['error'] = stderr or ('脚本无输出' if not stdout else f'stdout: {stdout}')

    except Exception as e:
        exec_result['status'] = 'error'
        exec_result['error'] = str(e)
    finally:
        exec_result['duration'] = round(time.time() - start_time, 3)

        # 收集截图路径
        if screenshot_enabled and screenshots_dir.exists():
            screenshots = sorted(screenshots_dir.glob('*.png'))
            if screenshots:
                exec_result['screenshot_path'] = str(screenshots[-1])  # 最后一张截图

        # 清理临时目录（保留截图用于展示）
        # shutil.rmtree(results_dir, ignore_errors=True)

    return exec_result


def _normalize_cookies(cookies) -> list:
    """
    将各种 cookie 输入格式归一化为标准列表

    支持的格式：
    1. JSON 数组: [{"name":"sid","value":"xxx","domain":".doubao.com"}]
    2. Cookie 字符串: "sessionid=abc123; csrftoken=xyz"
    3. Netscape 格式 (cookies.txt): ".doubao.com\tTRUE\t/\tFALSE\t0\tsid\txxx"
    """
    import re
    if not cookies:
        return []

    # 已是 list 格式
    if isinstance(cookies, list):
        result = []
        for c in cookies:
            if isinstance(c, dict) and 'name' in c and 'value' in c:
                result.append({
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', ''),
                    'path': c.get('path', '/'),
                    'httpOnly': c.get('httpOnly', False),
                    'secure': c.get('secure', False),
                    'sameSite': c.get('sameSite', 'Lax'),
                })
        return result

    # 字符串格式
    if isinstance(cookies, str):
        cookies_str = cookies.strip()
        result = []
        # Netscape cookies.txt 格式 (tab 分隔)
        if '\t' in cookies_str:
            for line in cookies_str.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    result.append({
                        'name': parts[5],
                        'value': parts[6],
                        'domain': parts[0],
                        'path': parts[2],
                        'secure': parts[3] == 'TRUE',
                        'httpOnly': False,
                        'sameSite': 'Lax',
                    })
        else:
            # "name1=value1; name2=value2" 格式
            for pair in cookies_str.split(';'):
                pair = pair.strip()
                if '=' in pair:
                    name, value = pair.split('=', 1)
                    result.append({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '',
                        'path': '/',
                        'sameSite': 'Lax',
                    })
        return result

    return []


def _generate_cookie_injection_code(cookies: list, indent: str = '        ') -> str:
    """
    生成 cookie 注入的 Python 代码片段
    需要先对 cookies 做归一化处理
    """
    if not cookies:
        return f'{indent}# 无 Cookie 需要注入\n'

    cookie_dicts = json.dumps(cookies, ensure_ascii=False)
    code = f'''{indent}# ===== 注入 Cookie（登录态恢复）=====
{indent}cookies_to_set = json.loads({json.dumps(cookie_dicts)})
{indent}if cookies_to_set:
{indent}    try:
{indent}        await page.context.add_cookies(cookies_to_set)
{indent}        print(f"[Cookie] 成功注入 {{len(cookies_to_set)}} 个 Cookie", flush=True)
{indent}    except Exception as ck_err:
{indent}        print(f"[Cookie] 注入失败: {{ck_err}}", flush=True)
{indent}# ===== Cookie 注入结束 =====

'''
    return code


def _ai_prompt_to_steps(prompt: str, url: str) -> list:
    """
    AI 模式：将自然语言描述转换为结构化步骤
    支持的格式（每行一个动作）：
      打开 https://xxx.com 或 打开 xxx 页面
      点击 发送按钮 / 点击「登录」
      在 输入框 中输入 你好
      等待 3秒
      截图 / 全屏截图
      下滑 / 上滑
      按 Enter 键
      选择 下拉框 值为 xxx
      验证 页面包含 xxx

    选择器策略：
      通用UI组件名(输入框/搜索框/文本框) → get_by_role('textbox')
      按钮类(发送/提交/登录)          → get_by_role('button', name='...')
      精确页面文本                     → text='...'
    """
    import re

    # === 通用 UI 组件名映射到 Playwright Role ===
    INPUT_COMPONENTS = {'输入框', '搜索框', '文本框', '对话', '对话框', '输入区',
                        '消息框', '聊天框', '编辑框', '内容区', '正文'}
    BUTTON_KEYWORDS = {'发送', '提交', '确认', '取消', '删除', '保存', '登录',
                       '注册', '查询', '搜索', '下一步', '上一步', '关闭',
                       '按钮', '确定'}

    def _resolve_selector(target_text: str, action_type: str = 'click') -> str:
        """智能解析目标描述为 Playwright 选择器"""
        t = target_text.strip()
        if not t:
            return 'body'  # 兜底

        # 输入类组件 → textbox role
        is_input_component = any(kw in t for kw in INPUT_COMPONENTS)
        if action_type in ('fill', 'input') and is_input_component:
            return "role=textbox"

        # 提取按钮名称（去掉后缀「按钮」）
        btn_name = re.sub(r'按钮$', '', t).strip()

        # 纯通用按钮词（无具体名称）→ 直接用 button role
        if btn_name in ('发送', '提交', '确认', '取消', '登录', '注册',
                         '搜索', '查询', '关闭', '确定'):
            return f'role=button[name="{btn_name}"]'

        # 带修饰语的按钮（如「发送按钮」「蓝色提交按钮」）
        if any(kw in t for kw in BUTTON_KEYWORDS):
            return f'role=button[name="{btn_name}"]'

        # 其他情况：当作页面实际文本来匹配
        return f'text={json.dumps(t)}'

    steps = []
    lines = [l.strip() for l in prompt.strip().split('\n') if l.strip()]
    has_navigate = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # === 导航 ===
        nav_match = re.match(r'^打开\s*(.+?)(?:\s*页面)?$', line)
        if nav_match:
            target = nav_match.group(1).strip()
            if target.startswith('http') or '.' in target:
                steps.append({
                    'action': 'navigate',
                    'params': {'url': target},
                    'description': f'打开页面 {target}',
                })
                has_navigate = True
            else:
                steps.append({
                    'action': 'navigate',
                    'params': {'url': url},
                    'description': f'打开页面 {target}',
                })
                has_navigate = True
            continue

        # === 点击 ===
        click_match = re.match(r'^点击\s*(?:「(.+)」|["""](.+)["""]|(.+))$', line)
        if click_match or line.startswith('点击'):
            btn_text = (click_match.group(1) or click_match.group(2) or click_match.group(3)).strip() if click_match else ''
            if not btn_text:
                btn_text = re.sub(r'^点击[\s:：]*', '', line).strip()
            if btn_text:
                sel = _resolve_selector(btn_text, 'click')
                steps.append({
                    'action': 'click',
                    'params': {'selector': sel},
                    'description': f'点击 [{btn_text}]',
                })
            continue

        # === 输入/填写 ===
        fill_match = re.match(r'^在\s*(.+?)\s*(?:中|里)\s*(?:输入|填写|填入)\s*(.+)$', line)
        if fill_match or '输入' in line or '填写' in line:
            if fill_match:
                field_desc = fill_match.group(1).strip()
                value = fill_match.group(2).strip()
            else:
                parts = re.sub(r'^(?:输入|填写)[\s:：]*', '', line).split(None, 1)
                field_desc = parts[0] if parts else ''
                value = parts[1] if len(parts) > 1 else ''

            sel = _resolve_selector(field_desc, 'fill')
            steps.append({
                'action': 'fill',
                'params': {'selector': sel, 'value': value},
                'description': f'在 [{field_desc}] 中输入 [{value}]',
            })
            continue

        # === 选择下拉框 ===
        select_match = re.match(r'^选择\s*(.+?)\s*为\s*(.+)$', line)
        if select_match or line.startswith('选择'):
            if select_match:
                field_desc = select_match.group(1).strip()
                value = select_match.group(2).strip()
            else:
                parts = re.sub(r'^选择[\s:：]*', '', line).split('为', 1)
                field_desc = parts[0].strip() if parts else ''
                value = parts[1].strip() if len(parts) > 1 else ''
            sel = _resolve_selector(field_desc, 'select')
            steps.append({
                'action': 'select',
                'params': {'selector': sel, 'value': value},
                'description': f'选择 [{field_desc}] 为 [{value}]',
            })
            continue

        # === 等待 ===
        wait_match = re.match(r'^等待?\s*(\d+)\s*秒?$', line)
        if wait_match or '等待' in line:
            secs = int(wait_match.group(1)) if wait_match else 2
            steps.append({
                'action': 'wait_for',
                'params': {'time': secs * 1000},
                'description': f'等待 {secs} 秒',
            })
            continue

        # === 截图 ===
        if '截图' in line:
            full_page = '全屏' in line or '整页' in line or 'full' in line.lower()
            steps.append({
                'action': 'screenshot',
                'params': {'name': f'ai_step_{len(steps)+1}', 'full_page': full_page},
                'description': '全屏截图' if full_page else '截图',
            })
            continue

        # === 滚动 ===
        if any(kw in line for kw in ['下滑', '向下滚', 'scroll down']):
            steps.append({'action': 'scroll', 'params': {'direction': 'down'}, 'description': '向下滚动'})
            continue
        if any(kw in line for kw in ['上滑', '向上滚', 'scroll up']):
            steps.append({'action': 'scroll', 'params': {'direction': 'up'}, 'description': '向上滚动'})
            continue
        if '回到顶部' in line or '滚到顶部' in line:
            steps.append({'action': 'scroll', 'params': {'direction': 'top'}, 'description': '回到顶部'})
            continue

        # === 按键 ===
        key_match = re.match(r'^(?:按|按下|press)?[\s:：]*(\w+)\s*键?$', line)
        if key_match or any(kw in line for kw in ['按键', '按 Enter', '按回车', 'press']):
            key_map = {
                'enter': 'Enter', '回车': 'Enter', 'return': 'Enter',
                'tab': 'Tab', '制表': 'Tab',
                'escape': 'Escape', 'esc': 'Esc',
                'space': 'Space', '空格': ' ',
                'arrowdown': 'ArrowDown', '下箭头': 'ArrowDown',
                'arrowup': 'ArrowUp', '上箭头': 'ArrowUp',
            }
            raw_key = (key_match.group(1) if key_match else '').lower()
            key = key_map.get(raw_key, raw_key.capitalize() if raw_key else 'Enter')
            steps.append({
                'action': 'press_key',
                'params': {'key': key},
                'description': f'按下 {key} 键',
            })
            continue

        # === 验证/断言 ===
        if any(kw in line for kw in ['验证', '检查', '确认', 'assert']):
            steps.append({
                'action': 'wait_for',
                'params': {'time': 500},
                'description': f'[断言] {line}',
            })
            continue

    # 如果没有导航步骤，补一个默认导航
    if not has_navigate:
        steps.insert(0, {
            'action': 'navigate',
            'params': {'url': url},
            'description': f'打开目标页面 {url}',
        })

    if len(steps) <= 1:
        steps.append({
            'action': 'wait_for',
            'params': {'time': 2000},
            'description': '等待页面加载完成',
        })
        steps.append({
            'action': 'screenshot',
            'params': {'name': 'final'},
            'description': '执行结束截图',
        })

    return steps


def _generate_midscene_script(**kwargs) -> str:
    """
    生成使用 Midscene AI 视觉驱动的 Playwright 测试脚本

    Midscene 会截图 → 发送给 AI 视觉模型 → 理解页面 → 自动定位元素 → 执行操作
    无需手写选择器，直接用自然语言描述操作即可。
    """
    from django.conf import settings as _django_settings

    ai_prompt = kwargs['ai_prompt']
    target_url = kwargs['target_url']
    headless = kwargs['headless']
    viewport = kwargs['viewport']
    viewport_json = json.dumps(viewport)  # 预序列化，避免 f-string 模板二次转义
    screenshot_enabled = kwargs['screenshot_enabled']
    output_dir = kwargs['output_dir'].replace("\\", "/")
    screenshots_dir = kwargs['screenshots_dir'].replace("\\", "/")
    persistent_data_dir = kwargs.get('persistent_data_dir', '').replace("\\", "/")
    cookies_raw = kwargs.get('cookies', [])
    cookies_normalized = _normalize_cookies(cookies_raw)
    cookie_injection_code = _generate_cookie_injection_code(cookies_normalized, indent='            ')

    # 从 Django settings 读取 Midscene 配置（确保子进程也有正确的值）
    _provider = getattr(_django_settings, 'MIDSCENE_AI_PROVIDER', 'openai')
    _model = getattr(_django_settings, 'MIDSCENE_AI_MODEL', 'qwen-vl-max')
    _api_key = getattr(_django_settings, 'MIDSCENE_AI_API_KEY', '') or getattr(_django_settings, 'DASHSCOPE_API_KEY', '')
    _base_url = getattr(_django_settings, 'MIDSCENE_AI_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode')
    # Midscene 会自行拼接 /v1/chat/completions，所以 base_url 不能带 /v1 后缀
    _base_url = _base_url.rstrip('/')
    if _base_url.endswith('/v1'):
        _base_url = _base_url[:-3]

    # 将 prompt 按行拆分，过滤空行
    prompt_lines = [l.strip() for l in ai_prompt.strip().split('\n') if l.strip()]

    # 生成每行的 ai_action 调用（行首不缩进，由 textwrap.indent 统一处理）
    action_codes = []
    for i, line in enumerate(prompt_lines):
        safe_line = json.dumps(line, ensure_ascii=False)
        step_num = i + 1
        screenshot_path = os.path.join("SCREENSHOTS_DIR", f"step_{step_num}.png")
        action_codes.append(f'''# 步骤 {step_num}: {line}
print(f"[Midscene] 步骤 {step_num}: {{'{line}'}}", flush=True)
await agent.ai_action({safe_line})
# 截图记录该步骤执行后的页面状态
try:
    _ss_path = os.path.join(SCREENSHOTS_DIR, "step_{step_num}.png")
    await page.screenshot(path=_ss_path, full_page=False)
    step_results.append({{"step": {step_num}, "action": "ai_action", "status": "completed", "instruction": {safe_line}, "screenshot": _ss_path}})
except Exception as _ss_err:
    print(f"[Midscene] 步骤 {step_num} 截图失败: {{_ss_err}}", flush=True)
    step_results.append({{"step": {step_num}, "action": "ai_action", "status": "completed", "instruction": {safe_line}}})
print(f"[Midscene] 步骤 {step_num} 完成", flush=True)
''')

    script = f'''"""Auto-generated Midscene AI test script"""
import asyncio
import json
import os
import shutil
import sys
from playwright.async_api import async_playwright
from midscene import Agent
from midscene.web.playwright_page import PlaywrightWebPage
from midscene.core.ai_model import AIModelConfig
from midscene.core.types import AgentOptions

OUTPUT_DIR = r"{output_dir}"
RESULT_FILE = r"{output_dir}/result.json"
SCREENSHOTS_DIR = r"{screenshots_dir}"
TARGET_URL = {json.dumps(target_url)}
HEADLESS = {headless}
PERSISTENT_DATA_DIR = r"{persistent_data_dir}"

# Midscene AI 配置（由 Django 生成时直接注入，不依赖子进程环境变量）
MIDSCENE_PROVIDER = {_provider!r}
MIDSCENE_MODEL = {_model!r}
MIDSCENE_API_KEY = {_api_key!r}
MIDSCENE_BASE_URL = {_base_url!r}

# 双重保险：同时写入环境变量，兼容从环境变量读取的 Midscene 版本
os.environ['MIDSCENE_AI_PROVIDER'] = MIDSCENE_PROVIDER
os.environ['MIDSCENE_AI_MODEL'] = MIDSCENE_MODEL
os.environ['MIDSCENE_AI_API_KEY'] = MIDSCENE_API_KEY
if MIDSCENE_BASE_URL:
    os.environ['MIDSCENE_AI_BASE_URL'] = MIDSCENE_BASE_URL

async def main():
    step_results = []
    error_msg = None
    final_status = "passed"

    # 检测系统 Chromium（Playwright 默认查找 .local-browsers，国内服务器常被墙）
    _chromium_path = os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
    if not _chromium_path or not os.path.exists(_chromium_path):
        for _name in ('chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable'):
            _chromium_path = shutil.which(_name)
            if _chromium_path:
                break
    if _chromium_path:
        print(f"[Midscene] 使用系统 Chromium: {{_chromium_path}}", flush=True)
    else:
        print("[Midscene] 未找到系统 Chromium，依赖 Playwright 自带浏览器", flush=True)

    print("[Midscene] 启动浏览器（持久化上下文，保留登录状态）...", flush=True)

    async with async_playwright() as p:
        # 使用持久化浏览器上下文：cookies/localStorage 会保存到 PERSISTENT_DATA_DIR
        # 下次执行同一用户的数据时会自动恢复登录状态
        _launch_kwargs = dict(
            user_data_dir=PERSISTENT_DATA_DIR,
            headless=HEADLESS,
            viewport={viewport_json},
            accept_downloads=True,
        )
        if _chromium_path:
            _launch_kwargs['executable_path'] = _chromium_path
        context = await p.chromium.launch_persistent_context(**_launch_kwargs)
        page = context.pages[0] if context.pages else await context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(120000)  # SPA 页面加载慢，给足时间

        print(f"[Midscene] 持久化数据目录: {{PERSISTENT_DATA_DIR}}", flush=True)

        # 创建 Midscene Web Page 和 Agent
        web_page = PlaywrightWebPage(page, context, None)  # persistent_context 无独立 browser 对象

        model_config = AIModelConfig(
            provider=MIDSCENE_PROVIDER,
            model=MIDSCENE_MODEL,
            api_key=MIDSCENE_API_KEY,
            base_url=MIDSCENE_BASE_URL if MIDSCENE_BASE_URL else None,
            max_tokens=4000,
            temperature=0.1,
            timeout=60,
        )

        agent_options = AgentOptions(
            generate_report=False,
            auto_print_report_msg=False,
            model_config=lambda: model_config,
        )

        agent = Agent(web_page, agent_options)
        print(f"[Midscene] AI 模型: {{MIDSCENE_PROVIDER}}/{{MIDSCENE_MODEL}}", flush=True)

        try:
            # 导航到目标 URL (SPA 页面用 domcontentloaded，不用 networkidle 避免超时)
            print(f"[Midscene] 导航至: {{TARGET_URL}}", flush=True)

            # 注入 Cookie（在导航前）
{cookie_injection_code}
            try:
                await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=120000)
            except Exception as nav_err:
                print(f"[Midscene] 导航警告: {{nav_err}}", flush=True)
            await page.wait_for_timeout(3000)  # 等待页面 JS 渲染完成
            # 注意：导航步骤不加入 step_results，避免用户看到多余的"打开页面"
            # 导航截图保存为 initial.png（供调试用，不作为正式步骤截图）
            try:
                nav_screenshot_path = os.path.join(SCREENSHOTS_DIR, "step_0_initial.png")
                await page.screenshot(path=nav_screenshot_path, full_page=False)
                print(f"[Midscene] 导航截图已保存", flush=True)
            except Exception:
                pass

            # 逐行执行 AI 指令
{textwrap.indent(chr(10).join(action_codes), '            ')}

            # 最终截图
            if {screenshot_enabled}:
                screenshot_path = f"{{SCREENSHOTS_DIR}}/final.png"
                await page.screenshot(path=screenshot_path, type="png")
                print(f"[Midscene] 最终截图已保存: {{screenshot_path}}", flush=True)

            final_status = "passed"
            print("[Midscene] 所有步骤执行完成!", flush=True)

        except Exception as e:
            final_status = "error"
            error_msg = str(e)
            print(f"[Midscene] 执行失败: {{error_msg}}", flush=True)
            import traceback
            traceback.print_exc()

            # 失败时也截图
            if {screenshot_enabled}:
                try:
                    error_path = f"{{SCREENSHOTS_DIR}}/error.png"
                    await page.screenshot(path=error_path, type="png")
                except Exception:
                    pass

        await context.close()

    result = {{
        "status": final_status,
        "steps_results": step_results,
        "assertion_errors": [],
        "screenshot_path": f"{{SCREENSHOTS_DIR}}/final.png" if {screenshot_enabled} else None,
        "error": error_msg,
    }}

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 0=成功, 非0=失败
    if final_status == "passed":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
'''
    return script


def _selector_to_locator(selector: str) -> str:
    """
    将自定义选择器字符串转为 Playwright locator 表达式
    支持格式：
      role=textbox              → page.get_by_role("textbox")
      role=button[name="发送"]  → page.get_by_role("button", name="发送")
      text="你好"               → page.get_by_text("你好")
      #id                      → page.locator("#id")
      .class                    → page.locator(".class")
      其他                     → page.locator(selector)
    """
    if selector.startswith('role='):
        rest = selector[5:]
        # role=button[name="xxx"]
        m = re.match(r'^(\w+)\[name=(.+)\]$', rest)
        if m:
            return f'page.get_by_role("{m.group(1)}", name={json.dumps(m.group(2))})'
        # 纯 role
        return f'page.get_by_role("{rest}")'

    if selector.startswith('text='):
        inner = json.loads(selector[5:]) if selector[5:].startswith('"') else selector[5:]
        return f'page.get_by_text({json.dumps(inner)})'

    if selector.startswith('#') or selector.startswith('.') or selector.startswith('['):
        return f'page.locator({json.dumps(selector)})'

    # 默认用 locator
    return f'page.locator({json.dumps(selector)})'


def _generate_playwright_script(**kwargs):
    """生成完整的 Playwright 测试 Python 脚本"""

    target_url = kwargs['target_url']
    browser_type = kwargs['browser_type']
    headless = kwargs['headless']
    viewport = kwargs['viewport']
    steps = kwargs['steps']
    assertions = kwargs['assertions']
    screenshot_enabled = kwargs['screenshot_enabled']
    full_page_screenshot = kwargs['full_page_screenshot']
    record_video = kwargs['record_video']
    output_dir = kwargs['output_dir']
    screenshots_dir = kwargs['screenshots_dir']
    persistent_data_dir = kwargs.get('persistent_data_dir', '')
    cookies_raw = kwargs.get('cookies', [])
    cookies_normalized = _normalize_cookies(cookies_raw)
    cookie_injection_code = _generate_cookie_injection_code(cookies_normalized, indent='        ')

    # 规范化路径（Windows 兼容：正斜杠避免转义问题）
    _out = output_dir.replace("\\", "/")
    _scr = screenshots_dir.replace("\\", "/")

    # 生成步骤代码块
    step_codes = []
    for idx, step in enumerate(steps):
        action = step.get('action', '')
        params = step.get('params', {})
        desc = step.get('description', '')

        code = f"    # Step {idx + 1}: {desc}\n"

        if action == 'navigate':
            code += f"    await page.goto('{params.get('url', target_url)}')"
        elif action == 'click':
            selector = params.get('selector', params.get('value', 'body'))
            loc = _selector_to_locator(selector)
            code += f"    await {loc}.click(timeout=10000)"
        elif action == 'fill':
            selector = params.get('selector', 'body')
            value = params.get('value', '')
            loc = _selector_to_locator(selector)
            code += f"    await {loc}.fill({json.dumps(str(value))}, timeout=10000)"
        elif action == 'select':
            selector = params.get('selector', 'body')
            value = params.get('value', '')
            loc = _selector_to_locator(selector)
            code += f"    await {loc}.select_option({json.dumps(str(value))}, timeout=10000)"
        elif action == 'hover':
            selector = params.get('selector', 'body')
            loc = _selector_to_locator(selector)
            code += f"    await {loc}.hover(timeout=10000)"
        elif action == 'wait_for':
            wait_type = params.get('type', 'time')
            if wait_type == 'time':
                code += f"    await page.wait_for_timeout({params.get('time', 1000)})"
            elif wait_type == 'selector':
                code += f"    await page.wait_for_selector({json.dumps(params.get('selector', ''))})"
            elif wait_type == 'network':
                code += f"    await page.wait_for_load_state({json.dumps(params.get('state', 'networkidle'))})"
        elif action == 'screenshot':
            name = params.get('name', f'step_{idx + 1}')
            fp_mode = 'full_page=True, ' if params.get('full_page') else ''
            code += f"    await page.screenshot(path=r'{_scr}/{name}.png', {fp_mode}type='png')"
        elif action == 'scroll':
            direction = params.get('direction', 'down')
            amount = params.get('amount', 500)
            if direction == 'down':
                code += f"    await page.mouse.wheel(0, {amount})"
            elif direction == 'up':
                code += f"    await page.mouse.wheel(0, -{amount})"
            elif direction == 'top':
                code += "    await page.evaluate('window.scrollTo(0, 0)')"
            else:
                code += f"    await page.mouse.wheel(0, {amount})"
        elif action == 'press_key':
            key = params.get('key', 'Enter')
            code += f"    await page.keyboard.press({json.dumps(key)})"
        elif action == 'upload_file':
            selector = params.get('selector', 'input[type="file"]')
            file_path = params.get('file_path', '')
            code += f"""    with page.expect_file_chooser() as fc_info:
        await page.click({json.dumps(selector)})
    file_chooser = await fc_info.value
    await file_chooser.set_files({json.dumps(file_path)})"""
        elif action == 'execute_js':
            script = params.get('script', '')
            code += f"    await page.evaluate({json.dumps(script)})"
        else:
            code += f"    pass  # unknown action: {action}"

        # 每步之后记录结果
        code += f"\n    step_results.append({{'step': {idx + 1}, 'action': '{action}', 'status': 'completed'}})\n\n"
        step_codes.append(code)

    # 生成断言代码块
    assertion_codes = []
    for idx, assertion in enumerate(assertions):
        atype = assertion.get('type', '')
        code = f"    # Assertion {idx + 1}\n"

        if atype == 'url_contains':
            code += f"""    current_url = page.url
    assert {json.dumps(assertion.get('value', ''))} in current_url, f"URL断言失败: 期望包含 {{assertion['value']}}, 实际 {{current_url}}\""""
        elif atype == 'url_match':
            import re
            pattern = assertion.get('value', '')
            code += f"    assert re.search({json.dumps(pattern)}, page.url), f'URL正则断言失败: 不匹配 {pattern}'\n    import re"
        elif atype == 'text_exists':
            val = assertion.get('expected', assertion.get('value', ''))
            selector = assertion.get('selector')
            if selector:
                content = await_code = f"await page.text_content({json.dumps(selector)}) or ''"
            else:
                await_code = f"await page.content()"
            code += f"    text_content = ({await_code})\n    assert {json.dumps(val)} in text_content, f'文本断言失败: 未找到 {val}'"
        elif atype == 'element_visible':
            selector = assertion.get('selector', assertion.get('value', ''))
            code += f"    element = await page.query_selector({json.dumps(selector)})\n    assert element is not None, f'元素可见性断言失败: 找不到 {selector}'\n    assert await element.is_visible(), f'元素可见性断言失败: 元素不可见'"
        elif atype == 'element_count':
            selector = assertion.get('selector', assertion.get('value', ''))
            expected = assertion.get('expected', 1)
            code += f"    count = len(await page.query_selector_all({json.dumps(selector)}))\n    assert count >= int({expected}), f'元素数量断言失败: 期望>={expected}, 实际={{count}}'"

        assertion_codes.append(code + "\n")

    _persist = persistent_data_dir.replace("\\", "/") if persistent_data_dir else ''

    script = f'''"""Auto-generated Playwright test script"""
import asyncio
import json
import os
import re
import shutil
from playwright.async_api import async_playwright

OUTPUT_DIR = r"{_out}"
RESULT_FILE = r"{_out}/result.json"
SCREENSHOTS_DIR = r"{_scr}"
PERSISTENT_DATA_DIR = r"{_persist}"
STEPS_DATA = json.loads(json.dumps({json.dumps(steps, ensure_ascii=False)}, ensure_ascii=False))[1:-1]
ASSERTIONS_DATA = json.loads(json.dumps({json.dumps(assertions, ensure_ascii=False)}, ensure_ascii=False))[1:-1]

async def main():
    step_results = []
    assertion_errors = []

    # 检测系统 Chromium（Playwright 默认查找 .local-browsers，国内服务器常被墙）
    _chromium_path = os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
    if not _chromium_path or not os.path.exists(_chromium_path):
        for _name in ('chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable'):
            _chromium_path = shutil.which(_name)
            if _chromium_path:
                break
    if _chromium_path:
        print(f"[Playwright] 使用系统 Chromium: {{_chromium_path}}", flush=True)
    else:
        print("[Playwright] 未找到系统 Chromium，依赖 Playwright 自带浏览器", flush=True)

    print("[Playwright] 启动浏览器（持久化上下文，保留登录状态）...", flush=True)

    async with async_playwright() as p:
        # 使用持久化浏览器上下文：cookies/localStorage 会自动保存和恢复
        _launch_kwargs = dict(
            user_data_dir=PERSISTENT_DATA_DIR,
            headless={headless},
            viewport={json.dumps(viewport)},
            accept_downloads=True,
        )
        if _chromium_path:
            _launch_kwargs['executable_path'] = _chromium_path
        context = await p.{browser_type}.launch_persistent_context(**_launch_kwargs)
        page = context.pages[0] if context.pages else await context.new_page()

        print(f"[Playwright] 持久化数据目录: {{PERSISTENT_DATA_DIR}}", flush=True)

        # 设置默认超时
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            # ========== 注入 Cookie ==========
{cookie_injection_code}
            # ========== 执行步骤 ==========
{textwrap.indent(chr(10).join(step_codes), '        ')}

            # ========== 执行断言 ==========
{textwrap.indent(chr(10).join(assertion_codes), '        ')}
            
            final_status = "passed"

        except AssertionError as e:
            final_status = "failed"
            assertion_errors.append(str(e))
        except Exception as e:
            final_status = "error"
            error_msg = str(e)
        
        # 最终截图
        if {screenshot_enabled}:
            try:
                await page.screenshot(
                    path=f"{{SCREENSHOTS_DIR}}/final.png",
                    type="png",
                    full_page={full_page_screenshot}
                )
            except Exception:
                pass

        await context.close()

    # 写入结果
    result = {{
        "status": final_status,
        "steps_results": step_results,
        "assertion_errors": assertion_errors,
        "screenshot_path": f"{{SCREENSHOTS_DIR}}/final.png" if {screenshot_enabled} else None,
        "video_path": None,
        "error": locals().get("error_msg", None),
    }}

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
'''

    return script
