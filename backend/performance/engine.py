"""
性能测试引擎 — 基于 Locust 编程式 API
动态生成 HttpUser，运行压测并收集统计指标
"""
import time
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class PerfTestEngine:
    """性能测试执行引擎 — 使用 Locust 编程式 API"""

    def __init__(self, execution):
        self.execution = execution
        self._stop_flag = threading.Event()
        self._runner_thread = None

    def run_async(self):
        """异步启动执行（在新线程中运行）"""
        self._runner_thread = threading.Thread(target=self._run, daemon=True)
        self._runner_thread.start()
        return self._runner_thread

    def stop(self):
        """停止执行"""
        self._stop_flag.set()

    def is_running(self):
        return self._runner_thread and self._runner_thread.is_alive()

    def _run(self):
        """核心执行逻辑 — 避免在 Django 进程中导入 Locust（gevent monkey-patch 会污染主进程）"""
        try:
            test_case = self.execution.test_case
            if test_case.test_type == 'ramp':
                self._run_ramp_fallback()
            elif test_case.test_type in ('spike', 'stress'):
                # 尖峰/压力测试暂用基准模式（待后续实现专用引擎）
                self._run_baseline_fallback()
            elif test_case.test_type == 'mixed':
                self._run_mixed_fallback()
            else:
                self._run_baseline_fallback()
        except Exception as e:
            logger.error(f"性能测试执行异常: {e}")
            self._fail_execution(str(e))

    def _run_locust(self, Environment, HttpUser, task, between, events, gevent):
        """Locust 真实压测模式（已废弃，保留代码供参考）"""
        from django.utils import timezone as django_tz

        test_case = self.execution.test_case
        target_url = test_case.target_url
        method = test_case.method
        headers = test_case.headers or {}
        body = test_case.body
        execution = self.execution  # 闭包捕获

        # 预先解析 base URL（提取 scheme+host）
        from urllib.parse import urlparse
        parsed = urlparse(target_url)
        base_host = f"{parsed.scheme}://{parsed.netloc}"
        request_path = parsed.path + (f"?{parsed.query}" if parsed.query else "")

        class PerfUser(HttpUser):
            host = base_host
            wait_time = between(0, 0.01)

            @task
            def test_endpoint(self):
                req_body = body if method in ('POST', 'PUT', 'PATCH') else None
                with self.client.request(
                    method, request_path,
                    headers=headers,
                    json=req_body,
                    name=target_url,
                    catch_response=True
                ) as resp:
                    if resp.status_code >= 400:
                        resp.failure(f"HTTP {resp.status_code}")

        # 初始化 Locust 环境
        env = Environment(user_classes=[PerfUser])
        runner = env.create_local_runner()

        env.events.init.fire(environment=env, runner=runner, web_ui=None)

        # 启动压测
        runner.start(user_count=test_case.users, spawn_rate=test_case.spawn_rate)
        start_time = time.time()
        timeline = []

        try:
            while time.time() - start_time < test_case.duration:
                if self._stop_flag.is_set():
                    logger.info("收到停止信号，终止压测")
                    break

                gevent.sleep(1)
                elapsed = int(time.time() - start_time)
                stats = env.stats.total

                # 收集每秒指标
                point = {
                    'timestamp': elapsed,
                    'rps': round(stats.current_rps or 0, 2),
                    'users': runner.user_count,
                    'p50': round(stats.get_current_response_time_percentile(0.5) or 0, 1),
                    'p95': round(stats.get_current_response_time_percentile(0.95) or 0, 1),
                    'p99': round(stats.get_current_response_time_percentile(0.99) or 0, 1),
                    'avg': round(stats.avg_response_time or 0, 1),
                    'failures_per_sec': round(stats.current_fail_per_sec or 0, 2),
                }
                timeline.append(point)

                # 实时更新数据库
                execution.metrics_timeline = timeline
                execution.total_requests = stats.num_requests
                execution.requests_per_second = round(stats.total_rps or 0, 2)
                execution.failures = stats.num_failures
                execution.save(update_fields=[
                    'metrics_timeline', 'total_requests',
                    'requests_per_second', 'failures'
                ])
        finally:
            runner.stop()
            gevent.sleep(0.5)

        # 收集最终统计
        stats = env.stats.total
        self._save_final_stats(stats, timeline, stopped=self._stop_flag.is_set())
        env.events.quit.fire(environment=env, runner=runner)


    def _run_baseline_fallback(self):
        """基准测试 — 固定并发模式"""
        self._run_fallback_impl(self.execution.test_case.users, self.execution.test_case.duration)

    def _run_mixed_fallback(self):
        """混合场景 — 多接口按权重配比并发压测"""
        import time as _time
        test_case = self.execution.test_case
        scenarios = test_case.mixed_scenarios or []

        if not scenarios:
            self._fail_execution("混合场景未配置任何接口")
            return

        # 计算总权重和各场景实际并发数
        total_weight = sum(s.get('weight', 0) for s in scenarios)
        if total_weight <= 0:
            self._fail_execution("混合场景权重总和必须大于0")
            return

        # 按权重分配并发数，至少保证1个并发
        distribution = []
        remaining = test_case.users
        for i, sc in enumerate(scenarios):
            w = sc.get('weight', 0)
            if i == len(scenarios) - 1:
                users = max(remaining, 0)  # 最后一个拿剩下的
            else:
                users = max(int(test_case.users * w / total_weight), 0)
            remaining -= users
            if users > 0:
                distribution.append({**sc, 'assigned_users': users})

        if not distribution:
            self._fail_execution("混合场景各接口分配的并发数均为0")
            return

        # 修改执行日志头部
        log_lines = [f"[混合场景] 总并发={test_case.users}, 场景数={len(distribution)}, 总权重={total_weight}"]
        for i, ds in enumerate(distribution):
            log_lines.append(
                f"  场景{i+1}: {ds['method']} {ds['url']} "
                f"权重={ds['weight']} → 分配并发={ds['assigned_users']}"
            )
        mixed_log = '\n'.join(log_lines) + '\n'

        all_timeline = []
        all_response_times = []
        total_req = 0
        total_fail = 0

        global_start = _time.time()

        # 各场景使用独立线程池并行执行
        import concurrent.futures
        import threading

        results_lock = threading.Lock()

        def run_scenario(scenario, users, duration):
            """在独立线程中运行单个场景"""
            try:
                import requests as req_lib
            except ImportError:
                return [], [], 0, 0

            sc_timeline = []
            sc_times = []
            sc_req = [0]
            sc_fail = [0]

            method = scenario.get('method', 'GET')
            url = scenario.get('url', '')
            sc_headers = scenario.get('headers') or {}
            sc_body = scenario.get('body')

            if not url:
                return [], [], 0, 0

            start = _time.time()

            def make_request():
                try:
                    req_start = _time.time()
                    kwargs = {
                        'method': method,
                        'url': url,
                        'headers': sc_headers,
                        'timeout': 30,
                    }
                    if method in ('POST', 'PUT', 'PATCH') and sc_body:
                        kwargs['json'] = sc_body
                    resp = req_lib.request(**kwargs)
                    elapsed_ms = (_time.time() - req_start) * 1000
                    sc_times.append(elapsed_ms)
                    sc_req[0] += 1
                    if resp.status_code >= 400:
                        sc_fail[0] += 1
                    return elapsed_ms
                except Exception:
                    sc_fail[0] += 1
                    sc_req[0] += 1
                    return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=users * 2) as pool:
                futures = []
                while _time.time() - start < duration and not self._stop_flag.is_set():
                    while len(futures) - sum(1 for f in futures if f.done()) < users:
                        futures.append(pool.submit(make_request))
                    _time.sleep(1)
                    elapsed = int(_time.time() - start)
                    done_futures = [f for f in futures if f.done()]
                    rps_this_sec = len(done_futures)
                    recent = sc_times[-rps_this_sec:] if rps_this_sec > 0 and sc_times else []
                    sorted_t = sorted([t for t in recent if t is not None])
                    point = {
                        'timestamp': elapsed,
                        'rps': rps_this_sec,
                        'users': users,
                        'scenario': url[:50],
                        'p50': round(sorted_t[len(sorted_t)//2], 1) if sorted_t else 0,
                        'p95': round(sorted_t[int(len(sorted_t)*0.95)], 1) if len(sorted_t) >= 20 else 0,
                        'p99': round(sorted_t[int(len(sorted_t)*0.99)], 1) if len(sorted_t) >= 100 else 0,
                        'avg': round(sum(recent)/len(recent), 1) if recent else 0,
                        'failures_per_sec': 0,
                    }
                    sc_timeline.append(point)
                    futures = [f for f in futures if not f.done()]

                    # 实时更新数据库
                    with results_lock:
                        execution = self.execution
                        all_timeline_merged = sorted(all_timeline + sc_timeline, key=lambda x: x['timestamp'])[-60:]
                        execution.metrics_timeline = all_timeline_merged
                        execution.total_requests = sum(sr[0] for _, _, sr, _ in [(0, 0, sc_req, 0)] + [])
                        # 简化实时更新
                        execution.save(update_fields=['metrics_timeline'])

                concurrent.futures.wait(futures, timeout=10)

            return sc_timeline, sc_times, sc_req[0], sc_fail[0]

        # 并行运行所有场景
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(distribution)) as pool:
            future_map = {}
            for i, ds in enumerate(distribution):
                f = pool.submit(run_scenario, ds, ds['assigned_users'], test_case.duration)
                future_map[f] = i

            for f in concurrent.futures.as_completed(future_map):
                i = future_map[f]
                sc_timeline, sc_times, sc_req, sc_fail = f.result()
                # 标记时间戳偏移避免重叠
                base_offset = i * 0.001
                for pt in sc_timeline:
                    pt['timestamp'] = round(pt['timestamp'] + base_offset, 3)
                    pt['scenario_index'] = i
                all_timeline.extend(sc_timeline)
                all_response_times.extend(sc_times)
                total_req += sc_req
                total_fail += sc_fail

        # 按时间戳排序输出
        all_timeline.sort(key=lambda x: x['timestamp'])

        elapsed = max(_time.time() - global_start, 0.1)
        self._finalize_execution(all_response_times, all_timeline, total_req, total_fail, elapsed,
                                 log_extra=mixed_log)

    def _run_ramp_fallback(self):
        """梯度增压 — 从1用户逐步增加到最大并发"""
        import time as _time
        test_case = self.execution.test_case
        max_users = test_case.users
        step_users = test_case.ramp_step_users or 5
        step_duration = test_case.ramp_step_duration or 30

        current_users = 1
        all_timeline = []
        all_response_times = []
        total_req = 0
        total_fail = 0

        global_start = _time.time()
        ramp_log = f"[梯度增压] 最大并发={max_users}, 步长={step_users}, 每步{step_duration}s\n"

        while current_users <= max_users and not self._stop_flag.is_set():
            ramp_log += f"\n--- 阶梯: {current_users} 并发, 持续 {step_duration}s ---\n"

            # 临时覆盖并发参数
            step_timeline, step_resp_times, step_req, step_fail = self._run_single_step(
                current_users, step_duration
            )

            # 标记阶梯
            for pt in step_timeline:
                pt['step_users'] = current_users
            all_timeline.extend(step_timeline)
            all_response_times.extend(step_resp_times)
            total_req += step_req
            total_fail += step_fail

            current_users += step_users

        # 汇总最终结果
        elapsed = max(_time.time() - global_start, 0.1)
        self._finalize_execution(all_response_times, all_timeline, total_req, total_fail, elapsed,
                                 log_extra=ramp_log)

    def _run_single_step(self, users, duration):
        """执行单个固定并发的压测步骤，返回 (timeline, response_times, total_req, total_fail)"""
        import time as _time
        import concurrent.futures
        import random

        try:
            import requests as req_lib
        except ImportError:
            self._fail_execution("requests 库未安装")
            return [], [], 0, 0

        test_case = self.execution.test_case
        start_time = _time.time()
        timeline = []
        total_req = [0]
        total_fail = [0]
        response_times = []

        def make_request():
            try:
                req_start = _time.time()
                kwargs = {
                    'method': test_case.method,
                    'url': test_case.target_url,
                    'headers': test_case.headers or {},
                    'timeout': 30,
                }
                if test_case.method in ('POST', 'PUT', 'PATCH') and test_case.body:
                    kwargs['json'] = test_case.body
                resp = req_lib.request(**kwargs)
                elapsed_ms = (_time.time() - req_start) * 1000
                response_times.append(elapsed_ms)
                total_req[0] += 1
                if resp.status_code >= 400:
                    total_fail[0] += 1
                return elapsed_ms
            except Exception:
                total_fail[0] += 1
                total_req[0] += 1
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=users * 2) as pool:
            futures = []
            while _time.time() - start_time < duration:
                if self._stop_flag.is_set():
                    break
                while len(futures) - sum(1 for f in futures if f.done()) < users:
                    futures.append(pool.submit(make_request))
                _time.sleep(1)
                elapsed = int(_time.time() - start_time)
                done = [f for f in futures if f.done()]
                rps_this_second = len(done)
                recent_times = response_times[-rps_this_second:] if rps_this_second > 0 and response_times else []
                sorted_times = sorted([t for t in recent_times if t is not None])
                point = {
                    'timestamp': elapsed,
                    'rps': rps_this_second,
                    'users': users,
                    'p50': round(sorted_times[len(sorted_times)//2], 1) if sorted_times else 0,
                    'p95': round(sorted_times[int(len(sorted_times)*0.95)], 1) if len(sorted_times) >= 20 else 0,
                    'p99': round(sorted_times[int(len(sorted_times)*0.99)], 1) if len(sorted_times) >= 100 else 0,
                    'avg': round(sum(recent_times)/len(recent_times), 1) if recent_times else 0,
                    'failures_per_sec': 0,
                }
                timeline.append(point)
                execution = self.execution
                execution.metrics_timeline = timeline
                execution.total_requests = total_req[0]
                execution.failures = total_fail[0]
                if elapsed > 0:
                    execution.requests_per_second = round(total_req[0] / elapsed, 2)
                execution.save(update_fields=['metrics_timeline', 'total_requests', 'requests_per_second', 'failures'])
                futures = [f for f in futures if not f.done()]
            concurrent.futures.wait(futures, timeout=10)

        return timeline, list(response_times), total_req[0], total_fail[0]

    def _run_fallback_impl(self, users, duration):
        """基准固定并发实现"""
        step_timeline, step_resp_times, step_req, step_fail = self._run_single_step(users, duration)
        elapsed = max(duration, 1)
        self._finalize_execution(step_resp_times, step_timeline, step_req, step_fail, elapsed)

    def _finalize_execution(self, all_response_times, all_timeline, total_req, total_fail, elapsed, log_extra=''):
        """汇总最终执行结果"""
        from django.utils import timezone as django_tz
        execution = self.execution
        all_times = sorted([t for t in all_response_times if t is not None])

        execution.total_requests = total_req
        execution.failures = total_fail
        execution.requests_per_second = round(total_req / elapsed, 2) if elapsed > 0 else 0

        if all_times:
            n = len(all_times)
            execution.avg_response_time = round(sum(all_times) / n, 1)
            execution.min_response_time = round(all_times[0], 1)
            execution.max_response_time = round(all_times[-1], 1)
            execution.p50_response_time = round(all_times[n // 2], 1)
            execution.p90_response_time = round(all_times[int(n * 0.9)], 1)
            execution.p95_response_time = round(all_times[int(n * 0.95)], 1)
            execution.p99_response_time = round(all_times[int(n * 0.99)], 1)

        execution.metrics_timeline = all_timeline
        if log_extra:
            execution.execution_log += '\n' + log_extra
        self._check_thresholds(execution, all_times, total_fail, total_req,
                               stopped=self._stop_flag.is_set())
        execution.completed_at = django_tz.now()
        if self._stop_flag.is_set():
            execution.status = 'stopped'
            execution.execution_log += '\n[INFO] 用户手动停止了压测'
        execution.save()

        # 压测完成后异步触发 AI 诊断
        if not self._stop_flag.is_set() and execution.status in ('completed', 'failed'):
            self._trigger_ai_analysis(execution)

    def _save_final_stats(self, stats, timeline, stopped=False):
        """保存 Locust 模式的最终统计"""
        from django.utils import timezone as django_tz

        execution = self.execution
        execution.total_requests = stats.num_requests
        execution.failures = stats.num_failures
        execution.requests_per_second = round(stats.total_rps or 0, 2)
        execution.avg_response_time = round(stats.avg_response_time or 0, 1)
        execution.min_response_time = round(stats.min_response_time or 0, 1)
        execution.max_response_time = round(stats.max_response_time or 0, 1)
        execution.p50_response_time = round(stats.get_response_time_percentile(0.5) or 0, 1)
        execution.p90_response_time = round(stats.get_response_time_percentile(0.9) or 0, 1)
        execution.p95_response_time = round(stats.get_response_time_percentile(0.95) or 0, 1)
        execution.p99_response_time = round(stats.get_response_time_percentile(0.99) or 0, 1)
        execution.metrics_timeline = timeline

        # 检查阈值
        all_times = [execution.p50_response_time]  # 简化：用百分位值做阈值检查
        self._check_thresholds(execution, all_times, stats.num_failures, stats.num_requests,
                               stopped=stopped)
        execution.completed_at = django_tz.now()
        if stopped:
            execution.status = 'stopped'
            execution.execution_log += '\n[INFO] 用户手动停止了压测'
        execution.save()

        # Locust 模式也触发 AI 诊断
        if not stopped and execution.status in ('completed', 'failed'):
            self._trigger_ai_analysis(execution)

    def _check_thresholds(self, execution, all_times, failures, total_requests, stopped=False):
        """检查断言阈值"""
        test_case = self.execution.test_case
        errors = []

        avg_ms = sum(all_times) / len(all_times) if all_times else 0
        if avg_ms > test_case.max_avg_response_time:
            errors.append(f'平均响应时间 {avg_ms:.0f}ms 超过阈值 {test_case.max_avg_response_time}ms')

        if all_times:
            p95 = sorted(all_times)[int(len(all_times) * 0.95)] if len(all_times) >= 20 else all_times[-1]
            if p95 > test_case.max_p95_response_time:
                errors.append(f'P95响应时间 {p95:.0f}ms 超过阈值 {test_case.max_p95_response_time}ms')

        failure_rate = failures / max(total_requests, 1)
        if failure_rate > test_case.max_failure_rate:
            errors.append(f'失败率 {failure_rate:.1%} 超过阈值 {test_case.max_failure_rate:.1%}')

        execution.threshold_errors = errors
        execution.thresholds_passed = len(errors) == 0

        if not stopped:
            if errors:
                execution.status = 'failed'
                execution.execution_log += f'\n[阈值] 未通过: {" | ".join(errors)}'
            else:
                execution.status = 'completed'
                execution.execution_log += '\n[阈值] 全部通过'

    def _fail_execution(self, error_msg):
        """标记执行失败"""
        from django.utils import timezone as django_tz
        execution = self.execution
        execution.status = 'failed'
        execution.execution_log += f'\n[错误] {error_msg}'
        execution.completed_at = django_tz.now()
        execution.save()

    @staticmethod
    def _trigger_ai_analysis(execution):
        """异步触发 AI 性能诊断"""
        try:
            from .ai_analyzer import PerfAIAnalyzer
            PerfAIAnalyzer.analyze_async(execution)
        except Exception as e:
            logger.warning(f"触发 AI 诊断失败: {e}")
