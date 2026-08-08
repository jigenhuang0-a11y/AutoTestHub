import subprocess, os, time, json, base64, urllib.request
import websocket

HTML_PATH = r"d:\AI_Project\ai-test-platform\项目架构图_手机超清版.html"
OUT_PATH = r"d:\AI_Project\ai-test-platform\docs\architecture_ultra_hd.png"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9225

# Inject 2.5x zoom into HTML for ultra crisp text
with open(HTML_PATH, "r", encoding="utf-8") as f:
    content = f.read()
content = content.replace("<style>", "<style>\n  html { zoom: 2.5; }\n  body { min-width: 750px; }")
ZOOM_HTML = HTML_PATH.replace(".html", "_zoom.html")
with open(ZOOM_HTML, "w", encoding="utf-8") as f:
    f.write(content)

# Start Edge headless
proc = subprocess.Popen(
    [EDGE_EXE, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
     "--headless", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
     "--hide-scrollbars", ZOOM_HTML],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(4)

# Get WebSocket debugger URL
req = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list")
pages = json.loads(req.read())
ws_url = pages[0]["webSocketDebuggerUrl"]

ws = websocket.create_connection(ws_url)

def cdp(ws, method, params=None):
    ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1:
            return r

# Set initial viewport
cdp(ws, "Emulation.setDeviceMetricsOverride", {
    "width": 750, "height": 1200, "deviceScaleFactor": 1, "mobile": False
})
time.sleep(2)

# Get full page dimensions
m = cdp(ws, "Runtime.evaluate", {
    "expression": "JSON.stringify({w:document.documentElement.scrollWidth,h:document.documentElement.scrollHeight})"
})
size = json.loads(m["result"]["result"]["value"])
print(f"[INFO] Page dimensions: {size['w']} x {size['h']}")

# Resize to full page
cdp(ws, "Emulation.setDeviceMetricsOverride", {
    "width": size["w"], "height": size["h"], "deviceScaleFactor": 1, "mobile": False
})
time.sleep(1)

# Capture full page screenshot
ss = cdp(ws, "Page.captureScreenshot", {
    "format": "png", "captureBeyondViewport": True, "fromSurface": True
})
with open(OUT_PATH, "wb") as f:
    f.write(base64.b64decode(ss["result"]["data"]))

ws.close()
proc.terminate()

file_size = os.path.getsize(OUT_PATH)
print(f"[OK] Ultra HD PNG saved: {OUT_PATH}")
print(f"[*] Size: {file_size/1024/1024:.1f} MB")
print(f"[*] Resolution: {size['w']} x {size['h']} pixels (2.5x zoom)")
print(f"[*] Tip: Import this PNG into WeChat Read. Text is large and crisp.")
