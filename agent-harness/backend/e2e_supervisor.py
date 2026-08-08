"""
Supervisor-Worker 编排端到端验证（自包含）

运行方式（服务需已在 8001 启动）：
    cd agent-harness/backend
    python e2e_supervisor.py

验证内容：
    1. 登录拿 JWT
    2. /supervisor/invoke 同步编排：任务解析 + 多 Worker 调度 + 汇总
    3. /supervisor/stream 流式编排：抽样 SSE 事件序列
"""
import json
import time
import urllib.request
import urllib.error
import http.client
import os

BASE = "http://127.0.0.1:8001"
API = f"{BASE}/api/v1"
HERE = os.path.dirname(os.path.abspath(__file__))


def _post_json(path, body, token=None, timeout=300):
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def main():
    print("== 1. 登录 ==")
    _, b = _post_json("/auth/login", {"username": "admin", "password": "admin123456"})
    token = json.loads(b)["access"]
    print(f"token len={len(token)}")

    print("\n== 2. /supervisor/invoke 同步编排 ==")
    payload = {"request": {
        "user_request": "先检索团队已有登录模块的测试用例，再补充生成遗漏的边界场景用例，最后评估覆盖率",
        "team_id": "default",
    }}
    t0 = time.time()
    s, b = _post_json("/supervisor/invoke", payload, token=token)
    print(f"status={s} elapsed={round(time.time()-t0,1)}s")
    if s == 200:
        r = json.loads(b)
        print("intent:", r.get("analysis", {}).get("intent"))
        print("required_workers:", r.get("analysis", {}).get("required_workers"))
        print("executed:", [w["worker"] for w in r.get("worker_results", [])])
        for w in r.get("worker_results", []):
            print(f"  - {w['worker']}: {w['status']}")
        # GBK 终端下非 ASCII（emoji 等）会崩溃，统一做安全打印
        final = str(r.get("final_output") or "")
        print("final_output(前400):", final.encode("ascii", "ignore").decode()[:400])
    else:
        print("ERR:", b[:400])

    print("\n== 3. /supervisor/stream 流式编排 ==")
    conn = http.client.HTTPConnection("127.0.0.1", 8001, timeout=300)
    body = json.dumps({"request": {
        "user_request": "生成一组注册接口的异常测试用例",
        "team_id": "default",
    }}).encode("utf-8")
    conn.request("POST", "/api/v1/supervisor/stream", body=body,
                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    resp = conn.getresponse()
    print(f"stream status={resp.status}")
    events, buf = [], b""
    start = time.time()
    while time.time() - start < 180:
        chunk = resp.read(1)
        if not chunk:
            break
        buf += chunk
        if b"\n\n" in buf:
            line, buf = buf.split(b"\n\n", 1)
            line = line.decode("utf-8", "replace")
            if line.startswith("data: "):
                try:
                    ev = json.loads(line[6:])
                    events.append(ev.get("event"))
                    print("  event:", ev.get("event"), "->", str(ev.get("data", ""))[:100].replace("\n", " "))
                except Exception:
                    pass
    print("事件序列:", events)
    conn.close()
    print("\n== 完成 ==")


if __name__ == "__main__":
    main()
