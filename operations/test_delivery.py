"""Outbox delivery tracking.

A queued message either goes out, retries with backoff, or ends up visibly
failed. The one thing that must never happen is silent loss.
"""

from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apiv1.tests import make_user
from operations.models import EmailDelivery
from operations.services import queue_email


class DeliveryTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def _queue(self, key="notice:1"):
        return queue_email(self.user, "Subject", "Body", key)

    def test_a_queued_message_is_sent_once_and_its_body_cleared(self):
        row = self._queue()
        call_command("deliver_email", verbosity=0)
        row.refresh_from_db()
        self.assertEqual(row.state, "sent")
        self.assertEqual(row.body, "")
        self.assertEqual(len(mail.outbox), 1)
        call_command("deliver_email", verbosity=0)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_transient_failure_retries_with_backoff(self):
        row = self._queue()
        with patch(
            "operations.management.commands.deliver_email.send_mail",
            side_effect=ConnectionError("smtp down"),
        ):
            call_command("deliver_email", verbosity=0, stderr=None)
        row.refresh_from_db()
        self.assertEqual(row.state, "queued")
        self.assertEqual(row.attempts, 1)
        self.assertEqual(row.last_error, "ConnectionError")
        self.assertGreater(row.available_at, timezone.now())

    def test_a_message_that_runs_out_of_retries_is_marked_failed(self):
        row = self._queue()
        EmailDelivery.objects.filter(pk=row.pk).update(
            attempts=EmailDelivery.MAX_ATTEMPTS - 1
        )
        with patch(
            "operations.management.commands.deliver_email.send_mail",
            side_effect=TimeoutError("gave up"),
        ):
            call_command("deliver_email", verbosity=0, stderr=None)
        row.refresh_from_db()
        self.assertEqual(row.state, "failed")
        self.assertEqual(row.last_error, "TimeoutError")
        self.assertEqual(row.body, "")

    def test_a_failed_message_is_not_retried_forever(self):
        row = self._queue()
        EmailDelivery.objects.filter(pk=row.pk).update(
            failed_at=timezone.now(), attempts=EmailDelivery.MAX_ATTEMPTS
        )
        call_command("deliver_email", verbosity=0)
        self.assertEqual(len(mail.outbox), 0)

    def test_queueing_the_same_key_twice_sends_one_message(self):
        self._queue("notice:same")
        self._queue("notice:same")
        self.assertEqual(EmailDelivery.objects.count(), 1)

    def test_a_message_scheduled_for_later_waits(self):
        row = self._queue()
        EmailDelivery.objects.filter(pk=row.pk).update(
            available_at=timezone.now() + timedelta(hours=1)
        )
        call_command("deliver_email", verbosity=0)
        self.assertEqual(len(mail.outbox), 0)
        row.refresh_from_db()
        self.assertEqual(row.state, "queued")
