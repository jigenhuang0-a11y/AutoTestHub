import subprocess
import time
import requests
import json
import base64
import os

HTML_PATH = r"d:\AI_Project\ai-test-platform\项目架构图_手机超清版.html"
OUT_PATH = r"d:\AI_Project\ai-test-platform\docs\architecture_ultra_hd.png"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

PORT = 9222

# 1. 启动 Edge headless with remote debugging
proc = subprocess.Popen(
    [EDGE_EXE,
     f"--remote-debugging-port={PORT}",
     "--headless",
     "--disable-gpu",
     "--no-sandbox",
     "--disable-dev-shm-usage",
     "--hide-scrollbars",
     HTML_PATH],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

time.sleep(3)

# 2. 获取 websocket debugger URL
r = requests.get(f"http://127.0.0.1:{PORT}/json/list")
pages = r.json()
ws_url = pages[0]["webSocketDebuggerUrl"]

# 3. 使用 simple websocket to send CDP commands
import websocket

def send_cdp(ws, method, params=None):
    msg = {"id": 1, "method": method, "params": params or {}}
    ws.send(json.dumps(msg))
    # Wait for response
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == 1:
            return resp

ws = websocket.create_connection(ws_url)

# 4. 设置 3x 分辨率 (deviceScaleFactor=3), viewport 750x 自动高度
# 先设置设备参数
send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
    "width": 750,
    "height": 1200,
    "deviceScaleFactor": 3,
    "mobile": True,
    "scale": 1,
})

# 5. 等待页面完全渲染
time.sleep(2)

# 6. 获取实际页面高度
metrics = send_cdp(ws, "Runtime.evaluate", {
    "expression": "JSON.stringify({width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight})"
})
result_str = metrics["result"]["result"]["value"]
size = json.loads(result_str)
page_width = size["width"]
page_height = size["height"]
print(f"Page size: {page_width}x{page_height}")

# 重新设置 viewport 高度为实际页面高度
send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
    "width": page_width,
    "height": page_height,
    "deviceScaleFactor": 3,
    "mobile": True,
    "scale": 1,
})

time.sleep(1)

# 7. 截取全页截图 (PNG)
screenshot = send_cdp(ws, "Page.captureScreenshot", {
    "format": "png",
    "captureBeyondViewport": True,
    "fromSurface": True,
})

img_data = base64.b64decode(screenshot["result"]["data"])
with open(OUT_PATH, "wb") as f:
    f.write(img_data)

ws.close()
proc.terminate()

file_size = os.path.getsize(OUT_PATH)
print(f"[OK] Ultra HD PNG saved: {OUT_PATH}")
print(f"[*] Size: {file_size/1024:.0f} KB ({file_size/1024/1024:.1f} MB)")
print(f"[*] Resolution: {page_width*3}x{page_height*3} @ 3x")
