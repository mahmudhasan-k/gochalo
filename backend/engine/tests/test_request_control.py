"""Rolling admission and session concurrency; no provider requests."""
from concurrent.futures import ThreadPoolExecutor
import unittest
from request_control import BudgetExceeded, FreeTierLimits, RequestBudget, SessionSubmission


class RequestBudgetTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.budget = RequestBudget(clock=lambda: self.now)
        self.scope = ("one-way-fingerprint", "gemini-3.5-flash-lite")

    def assert_limit(self, code, tokens=100):
        with self.assertRaises(BudgetExceeded) as caught:
            self.budget.reserve(self.scope, tokens)
        self.assertEqual(caught.exception.code, code)

    def test_defaults_are_local_minute_guards_not_provider_quota_claims(self):
        self.assertEqual(self.budget.limits, FreeTierLimits(15, 250_000, 2))

    def test_spacing_and_rolling_minute(self):
        for self.now in range(0, 30, 2):
            self.budget.reserve(self.scope, 100)
        self.now = 59.999
        self.assert_limit("local_rate_limit")
        self.now = 60
        self.budget.reserve(self.scope, 100)

    def test_same_session_can_exceed_former_session_and_shared_daily_caps(self):
        session = SessionSubmission()
        for attempt in range(100):
            self.now = attempt * 12
            self.budget.reserve(self.scope, 100, session=session)
        self.assertFalse(hasattr(session, "_daily_attempts"))
        self.assertEqual(len(self.budget._usage[self.scope].recent), 5)

    def test_token_window_and_rejected_requests_do_not_consume_capacity(self):
        self.budget.reserve(self.scope, 200_000)
        for _ in range(25):
            self.assert_limit("local_rate_limit")
        self.now = 12
        self.assert_limit("local_token_limit", 50_001)
        self.budget.reserve(self.scope, 50_000)
        self.assertEqual(len(self.budget._usage[self.scope].recent), 2)
        self.now = 60
        self.budget.reserve(self.scope, 200_000)

    def test_concurrent_sessions_cannot_double_reserve(self):
        def attempt(_):
            try:
                self.budget.reserve(self.scope, 100)
                return True
            except BudgetExceeded:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(16))), 1)

    def test_new_session_cannot_bypass_shared_cooldown(self):
        self.budget.reserve(self.scope, 100, session=SessionSubmission())
        with self.assertRaises(BudgetExceeded) as caught:
            self.budget.reserve(self.scope, 100, session=SessionSubmission())
        self.assertEqual(caught.exception.code, "local_rate_limit")
        self.assertEqual(self.budget.wait_seconds(self.scope), 2)

    def test_model_scopes_are_separate(self):
        self.budget.reserve(self.scope, 100)
        self.budget.reserve((self.scope[0], "another-model"), 100)

    def test_invalid_limits_and_token_reservations(self):
        with self.assertRaises(ValueError):
            FreeTierLimits(requests_per_minute=0)
        with self.assertRaises(ValueError):
            self.budget.reserve(self.scope, 0)


class SessionSubmissionTests(unittest.TestCase):
    def test_pending_consumed_once_and_lock_survives_rerun(self):
        session = SessionSubmission()
        self.assertTrue(session.queue())
        self.assertTrue(session.take_pending())
        self.assertFalse(session.take_pending())
        self.assertFalse(session.queue())
        session.finish()
        self.assertFalse(session.busy)
        self.assertTrue(session.queue())

    def test_concurrent_clicks_queue_once(self):
        session = SessionSubmission()
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(lambda _: session.queue(), range(16))), 1)
