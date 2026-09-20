from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from accounts.models import User
from network.models import CreatorConnection
from network.services import request_connection
from aiteam.views import _consume_allowance
from aiteam.models import DailyUsage


@skipUnlessDBFeature("has_select_for_update")
class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.users = []
        for index in range(2):
            user = User.objects.create_user(
                f"concurrent{index}@example.com",
                "correcthorsebattery1",
                f"Creator {index}",
            )
            user.email_verified_at = timezone.now()
            user.save()
            user.profile.published = True
            user.profile.save()
            self.users.append(user)

    def run_together(self, functions):
        barrier = Barrier(len(functions))

        def execute(fn):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return fn()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(functions)) as pool:
            return list(pool.map(execute, functions))

    def test_opposing_requests_create_one_pair_without_deadlock(self):
        a, b = self.users
        ids = self.run_together(
            [lambda: request_connection(a, b).pk, lambda: request_connection(b, a).pk]
        )
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(CreatorConnection.objects.count(), 1)

    def test_parallel_ai_requests_cannot_overrun_quota(self):
        with self.settings(AI_DAILY_LIMIT=1):
            outcomes = self.run_together(
                [
                    lambda: _consume_allowance(self.users[0]),
                    lambda: _consume_allowance(self.users[0]),
                ]
            )
        self.assertEqual(outcomes.count(""), 1)
        self.assertEqual(DailyUsage.objects.get().count, 1)
