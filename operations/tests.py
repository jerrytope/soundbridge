import json
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from django.core.management import call_command
from apiv1.tests import make_user
from operations.models import Notification, PrivacyRequest, EmailDelivery
from releases.models import ReleaseProject, ReleaseTask


class OperationsTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_reminders_are_deduplicated_and_respect_category(self):
        now = timezone.now().replace(hour=12)
        project = ReleaseProject.objects.create(
            owner=self.user, title="Album", date=now.date()
        )
        ReleaseTask.objects.create(
            release=project, title="Credits", due_date=now.date()
        )
        with patch(
            "operations.management.commands.send_reminders.timezone.now",
            return_value=now,
        ):
            call_command("send_reminders")
            call_command("send_reminders")
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(EmailDelivery.objects.count(), 0)

    def test_export_requires_password_and_records_completion(self):
        response = self.client.post(
            "/settings/privacy", {"password": "bad", "action": "export"}
        )
        self.assertContains(response, "Password is incorrect")
        self.assertEqual(PrivacyRequest.objects.count(), 0)
        response = self.client.post(
            "/settings/privacy",
            {"password": "correcthorsebattery1", "action": "export"},
        )
        payload = json.loads(response.content)
        self.assertIn("manual_income", payload)
        self.assertNotIn("password", payload["account"])
        self.assertEqual(PrivacyRequest.objects.get().state, "completed")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_deletion_is_tracked_not_falsely_completed(self):
        self.client.post(
            "/settings/privacy",
            {"password": "correcthorsebattery1", "action": "deletion"},
        )
        self.assertEqual(PrivacyRequest.objects.get().state, "pending")
        self.assertTrue(self.user.__class__.objects.filter(pk=self.user.pk).exists())

    def test_postgresql_free_plan_requires_approved_limits(self):
        from billing.models import Plan
        from billing.services import limit

        Plan.objects.create(
            code="free",
            name="Free",
            limits={"ai_daily": 3},
            approved_at=timezone.now(),
            commercial_terms="Test terms",
        )
        self.assertEqual(limit(self.user, "ai_daily"), 3)
        self.assertEqual(limit(self.user, "unknown"), 0)
