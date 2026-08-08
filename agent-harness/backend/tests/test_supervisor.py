"""
Supervisor-Worker 多代理编排层 —— 离线单元测试（不依赖 LLM / 网络 / Django）。

使用 unittest + mock.patch.object，直接替换 supervisor 模块内的 get_llm_router 与
workflow 模块内的 _execute_single_step，避免运行时 import 绑定导致 mock 失效。

覆盖：
1. analyze_task：用户请求 -> 结构化任务分析（required_workers / complexity）
2. decide_next：依据已完成 worker + pending 返回 dispatch / finish
3. run_supervisor 完整链路：search->generator->evaluator 串行，全部完成，status=completed
4. 失败自愈：worker 失败仅重试 MAX_RETRIES 次后停止，不再无限重排；status=partial/failed
5. 规则兜底：LLM router 不可用时 analyze_task 走关键词兜底

运行：python -m pytest tests/test_supervisor.py -q
"""
import sys
import types
import unittest
from unittest.mock import patch, MagicMock

import app.core.supervisor as sv


class FakeRouter:
    ANALYZE = (
        '{"intent":"为登录功能生成测试用例并评估覆盖率",'
        '"sub_goals":["检索已有用例","生成新用例","评估覆盖率"],'
        '"complexity":"medium",'
        '"required_workers":["search","generator","evaluator"]}'
    )
    DECIDE_SEQ = [
        '{"action":"dispatch","worker":"search","description":"检索登录功能已有用例","reason":"先查后生成"}',
        '{"action":"dispatch","worker":"generator","description":"生成登录功能测试用例","reason":"检索完成可生成"}',
        '{"action":"dispatch","worker":"evaluator","description":"评估生成用例覆盖率","reason":"生成完成可评估"}',
        '{"action":"finish","worker":null,"description":"","reason":"全部完成"}',
    ]

    def __init__(self, chat_error=False):
        self._k = 0
        self.summarize_return = "汇总结论：已完成登录功能用例生成与评估。"
        self.chat_error = chat_error

    def chat(self, messages, **kwargs):
        if self.chat_error:
            raise RuntimeError("LLM down")
        text = "\n".join(str(m.get("content", "")) for m in messages)
        if "分析器" in text or "任务编排分析器" in text:
            return self.ANALYZE
        if "汇总器" in text or "结果汇总器" in text:
            return self.summarize_return
        resp = self.DECIDE_SEQ[min(self._k, len(self.DECIDE_SEQ) - 1)]
        self._k += 1
        return resp


class SupervisorTest(unittest.TestCase):

    def setUp(self):
        self.router = FakeRouter()
        self.patcher = patch.object(sv, "get_llm_router", lambda: self.router)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    # 1
    def test_analyze_task_parses(self):
        sup = sv.Supervisor(team_id="default")
        a = sup.analyze_task("为登录功能生成测试用例并评估覆盖率")
        self.assertTrue(a.intent)
        self.assertIn("search", a.required_workers)
        self.assertIn("generator", a.required_workers)
        self.assertIn("evaluator", a.required_workers)
        self.assertEqual(a.complexity, "medium")

    # 2a
    def test_decide_next_dispatch(self):
        sup = sv.Supervisor(team_id="default")
        a = sup.analyze_task("为登录功能生成测试用例并评估覆盖率")
        d = sup.decide_next("req", a, [], list(a.required_workers))
        self.assertEqual(d["action"], "dispatch")
        self.assertEqual(d["worker"], "search")
        self.assertTrue(d["description"])

    # 2b
    def test_decide_next_finish(self):
        sup = sv.Supervisor(team_id="default")
        a = sup.analyze_task("为登录功能生成测试用例并评估覆盖率")
        done = [sv.WorkerResult("search", "d", "completed", {}),
                sv.WorkerResult("generator", "d", "completed", {}),
                sv.WorkerResult("evaluator", "d", "completed", {})]
        d = sup.decide_next("req", a, done, pending=[])
        self.assertEqual(d["action"], "finish")

    # 3 完整链路
    def test_run_supervisor_full_chain(self):
        import app.core.workflow as wf
        from unittest.mock import patch as _patch

        def fake_step(step, state):
            return {"status": "completed", "result": f"[{step.get('agent')}] output"}

        with _patch.object(wf, "_execute_single_step", side_effect=fake_step):
            r = sv.run_supervisor(
                user_request="为登录功能生成测试用例并评估覆盖率",
                task_id="t1", user_id="u1", auth_token="tok", team_id="default",
            )
        self.assertEqual(r["status"], "completed")
        workers = [x["worker"] for x in r["worker_results"]]
        self.assertEqual(workers, ["search", "generator", "evaluator"])
        self.assertTrue(all(x["status"] == "completed" for x in r["worker_results"]))
        self.assertTrue(r["final_output"])
        self.assertEqual(r["failed_workers"], [])

    # 4 失败自愈：generator 首次失败，重试一次后成功
    def test_run_supervisor_failure_cap(self):
        import app.core.workflow as wf
        from unittest.mock import patch as _patch

        fails = {"generator": 1}  # generator 还差 1 次失败才到重试上限

        def flaky(step, state):
            agent = step.get("agent")
            if agent in fails and fails[agent] > 0:
                fails[agent] -= 1
                raise RuntimeError("Django 503 模拟失败")
            return {"status": "completed", "result": "ok"}

        with _patch.object(wf, "_execute_single_step", side_effect=flaky):
            r = sv.run_supervisor(
                user_request="为登录功能生成测试用例并评估覆盖率",
                task_id="t2", user_id="u1", auth_token="tok", team_id="default",
            )
        # generator 重试后成功，整体应为 completed
        self.assertEqual(r["status"], "completed")
        st = {x["worker"]: x["status"] for x in r["worker_results"]}
        self.assertEqual(st["generator"], "completed")
        self.assertEqual(r["failed_workers"], [])
        # 不应出现无限重排：executed 中同种 worker 最多出现 2 次（原 1 + 重试 1）
        from collections import Counter
        cnt = Counter(x["worker"] for x in r["worker_results"])
        self.assertLessEqual(cnt["search"], 2)
        self.assertLessEqual(cnt["generator"], 2)

    # 4b 持续失败：达到重试上限后停止并标记 partial/failed
    def test_run_supervisor_persistent_failure(self):
        import app.core.workflow as wf
        from unittest.mock import patch as _patch

        def always_fail(step, state):
            raise RuntimeError("下游不可达")

        with _patch.object(wf, "_execute_single_step", side_effect=always_fail):
            r = sv.run_supervisor(
                user_request="为登录功能生成测试用例并评估覆盖率",
                task_id="t3", user_id="u1", auth_token="tok", team_id="default",
            )
        # 全部失败后状态应为 partial 或 failed，且不应无限重试（done 数量受控）
        self.assertIn(r["status"], ("partial", "failed"))
        self.assertTrue(r["failed_workers"])
        self.assertLessEqual(len(r["worker_results"]), 8)  # 受 max_workers 约束

    # 5 规则兜底
    def test_analyze_task_rule_fallback(self):
        err_router = FakeRouter(chat_error=True)
        with patch.object(sv, "get_llm_router", lambda: err_router):
            sup = sv.Supervisor(team_id="default")
            a = sup.analyze_task("请帮我生成登录功能的测试用例并评估")
        self.assertIn("generator", a.required_workers)
        self.assertIn("evaluator", a.required_workers)
        self.assertGreaterEqual(len(a.required_workers), 2)
        self.assertEqual(a.reasoning, "规则兜底（LLM 解析不可用）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
