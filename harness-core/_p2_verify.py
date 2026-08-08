from fastapi.testclient import TestClient
import harness_core.main as m

with TestClient(m.app) as c:
    print("health:", c.get("/health").json())
    print("plugins:", c.get("/plugins").json())

    r = c.post("/api/v1/generate/testcase", json={"requirement": "user login feature", "model": "deepseek-chat"})
    b = r.json()
    print("gen status:", r.status_code, "| cases:", len(b.get("cases", [])), "| final_state:", b.get("final_state"), "| paused:", b.get("paused"))
    tid = b.get("trace_id")
    print("trace spans:", c.get(f"/api/v1/traces/{tid}").json().get("span_count"))

    rag = c.post("/api/v1/rag/qa", json={
        "question": "how to reset password",
        "context": "User can click reset password in settings. System sends code to email.",
    })
    rb = rag.json()
    print("rag status:", rag.status_code, "| answer:", (rb.get("answer") or "")[:50])

    ev = c.post("/api/v1/eval/judge", json={
        "task": "generate login testcases",
        "output": "1. valid login 2. invalid login",
    })
    print("eval:", ev.json())
