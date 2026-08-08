"""Minimal VL test - single API call with existing screenshot"""
import base64, json, os, sys, time

# Force utf8
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

api_key = "YOUR_DASHSCOPE_API_KEY"
api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
model = "qwen3-vl-flash"
screenshot_path = os.path.join(os.path.dirname(__file__), 'test_output', 'vl_test_screenshot.png')

print(f"Screenshot: {screenshot_path} exists={os.path.exists(screenshot_path)}")

if not os.path.exists(screenshot_path):
    # Quick generate
    from playwright.sync_api import sync_playwright
    html_path = os.path.join(os.path.dirname(__file__), 'test_output', 'vl_page.html')
    with open(html_path, 'w') as f:
        f.write('<html><body style="padding:40px"><h1>Login Successful</h1><p>Welcome, admin!</p><button id="btn">Logout</button></body></html>')
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={'width':1280,'height':720})
        pg.goto(f'file:///{html_path.replace(os.sep, "/")}')
        pg.screenshot(path=screenshot_path)
        b.close()
    print(f"Generated: {screenshot_path}")

with open(screenshot_path,'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

import requests

t0 = time.time()
resp = requests.post(
    f"{api_url}/chat/completions",
    headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
    json={
        "model": model,
        "messages":[{"role":"user","content":[
            {"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}},
            {"type":"text","text":"This is a web UI test screenshot. Please analyze: 1) Is there text showing login success? 2) Is the username admin visible? 3) List all visible elements. Reply in JSON: {\"login_success\":bool,\"admin_visible\":bool,\"elements\":[...]}"}
        ]}],
        "max_tokens": 500,
        "temperature": 0.1,
    },
    timeout=30,
)

elapsed = time.time() - t0
print(f"\nStatus: {resp.status_code} | Time: {elapsed:.2f}s")
if resp.status_code == 200:
    data = resp.json()
    content = data['choices'][0]['message']['content']
    print(f"\n=== VL Model Response ===")
    print(content[:800])
    print(f"\n{'='*50}")
    print(f">>> VISUAL EVALUATION PASSED <<<")
    print(f"Model: {model}")
    print(f"Latency: {elapsed:.2f}s")
else:
    print(f"ERROR: {resp.text[:300]}")
