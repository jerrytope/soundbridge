"""The release gate.

`launch_check` must fail while anything real is missing, and must report the
reason rather than a generic refusal. It must also not invent readiness: an
approval record, not a code change, is what clears a decision gate.
"""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import StoredImage
from apiv1.tests import make_user
from operations.management.commands.launch_check import DECISIONS
from operations.models import LaunchDecision


def run_check():
    out = StringIO()
    try:
        call_command("launch_check", stdout=out)
        return out.getvalue(), None
    except CommandError as problem:
        return out.getvalue(), str(problem)


class LaunchCheckTests(TestCase):
    def test_a_fresh_workspace_is_blocked_and_says_why(self):
        output, failure = run_check()
        self.assertIsNotNone(failure)
        self.assertIn("not launch-certified", failure)
        self.assertIn("Missing approved decision/evidence: launch-markets", output)
        self.assertIn("Public HTTPS origin is not configured.", output)

    def test_every_listed_decision_is_reported_when_missing(self):
        output, _ = run_check()
        for key in DECISIONS:
            with self.subTest(key=key):
                self.assertIn(f"Missing approved decision/evidence: {key}", output)

    def test_an_unapproved_or_unowned_decision_does_not_count(self):
        LaunchDecision.objects.create(
            key="launch-markets", decision="Nigeria", owner="", approved_at=timezone.now()
        )
        output, _ = run_check()
        self.assertIn("Missing approved decision/evidence: launch-markets", output)

    def test_an_approved_decision_clears_its_gate(self):
        LaunchDecision.objects.create(
            key="launch-markets",
            decision="Nigeria and the United Kingdom",
            owner="Commercial lead",
            approved_at=timezone.now(),
        )
        output, _ = run_check()
        self.assertNotIn("Missing approved decision/evidence: launch-markets", output)

    def test_billing_and_policy_gates_are_reported(self):
        output, _ = run_check()
        self.assertIn("No payment provider adapter is configured", output)
        self.assertIn("No approved commercial plan exists", output)
        self.assertIn("No approved retention policy", output)

    def test_the_ai_evaluation_gate_wants_a_recorded_run(self):
        output, _ = run_check()
        self.assertIn("No AI evaluation run recorded", output)

    @override_settings(OPENAI_MODEL="gpt-4.1")
    def test_a_failing_evaluation_run_blocks(self):
        from aiteam.models import EvaluationRun

        EvaluationRun.objects.create(model="gpt-4.1", passed=3, failed=1)
        output, _ = run_check()
        self.assertIn("1 failing case", output)

    @override_settings(OPENAI_MODEL="gpt-4.1")
    def test_an_evaluation_against_another_model_blocks(self):
        from aiteam.models import EvaluationRun

        EvaluationRun.objects.create(model="gpt-4o", passed=3, failed=0)
        output, _ = run_check()
        self.assertIn("different model", output)

    def test_private_bytes_left_in_columns_block(self):
        user = make_user()
        StoredImage.objects.create(user=user, bytes=b"not-yet-moved", byte_size=13)
        output, _ = run_check()
        self.assertIn("1 private file(s) are still stored in database columns", output)

    def test_migrated_bytes_do_not_block(self):
        user = make_user()
        StoredImage.objects.create(user=user, bytes=b"x", byte_size=1)
        call_command("migrate_private_bytes", verbosity=0)
        output, _ = run_check()
        self.assertNotIn("still stored in database columns", output)
