import time

from django.test import TestCase

from agent_gateway.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, CircuitState


class CircuitBreakerTests(TestCase):
    """AI 编排服务熔断器单元测试"""

    def test_closed_state_allows_calls(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.can_call())

    def test_opens_after_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertFalse(cb.can_call())

    def test_success_resets_failure_count_in_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        cb.record_success()
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        time.sleep(0.15)
        self.assertTrue(cb.can_call())
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        self.assertTrue(cb.can_call())
        cb.record_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_half_open_failure_reopens_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        self.assertTrue(cb.can_call())
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertFalse(cb.can_call())

    def test_call_wrapper_records_success_and_failure(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)

        def ok():
            return "ok"

        def fail():
            raise ValueError("boom")

        self.assertEqual(cb.call(ok), "ok")
        with self.assertRaises(ValueError):
            cb.call(fail)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        with self.assertRaises(ValueError):
            cb.call(fail)
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_call_wrapper_rejects_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.record_failure()

        def ok():
            return "ok"

        with self.assertRaises(CircuitBreakerOpen):
            cb.call(ok)
