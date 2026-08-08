from fastapi.testclient import TestClient
import harness_core.main as m

with TestClient(m.app) as c:
    print("plugins:", c.get("/plugins").json())
    print("health phase:", c.get("/health").json().get("phase"))
    # metrics 结构（无调用时也应有骨架）
    met = c.get("/api/v1/metrics").json()
    print("metrics keys:", sorted(met.keys()))
    # 路由存在性
    paths = sorted({r.path for r in c.app.routes if hasattr(r, "path")})
    print("has multi:", "/api/v1/generate/testcase/multi" in paths)
    print("has sse:", "/api/v1/generate/testcase/stream" in paths)
    print("has metrics:", "/api/v1/metrics" in paths)
