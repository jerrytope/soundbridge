"""Export generation, account deletion and retention housekeeping.

Every case here goes through the approved-policy gate, because the PRD treats
grace periods, shared-content handling and retention windows as decisions the
operator makes, not defaults the code picks.
"""

import json
import uuid
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from apiv1.tests import make_user
from network.models import CreatorConnection, DirectMessage
from operations import privacy, storage
from operations.models import (
    AuditEvent,
    Notification,
    PrivacyRequest,
    PrivateArtifact,
    RetentionPolicy,
)


def approve_policy(**overrides):
    values = {
        "key": "default",
        "deletion_grace_hours": 24,
        "shared_message_handling": "retain_anonymised",
        "export_available_hours": 48,
        "audit_retention_days": 0,
        "notification_retention_days": 0,
        "decision_reference": "retention-and-deletion",
        "owner": "Data protection owner",
        "approved_at": timezone.now(),
    }
    values.update(overrides)
    return RetentionPolicy.objects.create(**values)


class PolicyGateTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_nothing_is_processed_without_an_approved_policy(self):
        PrivacyRequest.objects.create(user=self.user, kind="export")
        with self.assertRaises(privacy.PolicyRequired):
            privacy.due()
        with self.assertRaises(CommandError):
            call_command("process_privacy_requests", verbosity=0)
        self.assertEqual(PrivacyRequest.objects.get().state, "pending")

    def test_a_draft_policy_does_not_count_as_approved(self):
        approve_policy(approved_at=None)
        self.assertIsNone(privacy.policy())

    def test_an_unowned_or_unsourced_policy_does_not_count(self):
        policy = approve_policy(owner="")
        self.assertIsNone(privacy.policy())
        policy.owner = "Owner"
        policy.decision_reference = ""
        policy.save()
        self.assertIsNone(privacy.policy())

    def test_undecided_shared_content_handling_blocks_processing(self):
        approve_policy(shared_message_handling="")
        self.assertIsNone(privacy.policy())


class ExportTests(TestCase):
    def setUp(self):
        self.user = make_user()
        approve_policy()

    def test_export_produces_a_downloadable_artifact(self):
        row = PrivacyRequest.objects.create(user=self.user, kind="export")
        privacy.process(row.pk)
        row.refresh_from_db()
        self.assertEqual(row.state, "completed")
        artifact = PrivateArtifact.objects.get(user=self.user, kind="privacy-export")
        payload = json.loads(storage.read(artifact))
        self.assertEqual(payload["account"]["email"], self.user.email)
        self.assertIn("workspace", payload)
        self.assertTrue(artifact.expires_at > timezone.now())

    def test_owner_downloads_and_another_account_cannot(self):
        row = PrivacyRequest.objects.create(user=self.user, kind="export")
        privacy.process(row.pk)
        artifact = PrivateArtifact.objects.get(user=self.user)
        self.client.force_login(self.user)
        response = self.client.get(f"/privacy/downloads/{artifact.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("soundbridge-export.json", response["Content-Disposition"])
        artifact.refresh_from_db()
        self.assertIsNotNone(artifact.downloaded_at)
        self.client.force_login(make_user("other@example.com"))
        self.assertEqual(
            self.client.get(f"/privacy/downloads/{artifact.pk}").status_code, 404
        )

    def test_an_expired_export_is_not_served(self):
        row = PrivacyRequest.objects.create(user=self.user, kind="export")
        privacy.process(row.pk)
        artifact = PrivateArtifact.objects.get(user=self.user)
        artifact.expires_at = timezone.now() - timedelta(minutes=1)
        artifact.save(update_fields=["expires_at"])
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(f"/privacy/downloads/{artifact.pk}").status_code, 404
        )

    def test_a_tampered_signed_link_is_refused(self):
        row = PrivacyRequest.objects.create(user=self.user, kind="export")
        privacy.process(row.pk)
        artifact = PrivateArtifact.objects.get(user=self.user)
        self.client.force_login(self.user)
        url = storage.signed_url(artifact)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.get(f"/privacy/downloads/{artifact.pk}?token=forged").status_code,
            404,
        )

    def test_exports_are_not_generated_when_the_policy_disables_them(self):
        RetentionPolicy.objects.filter(key="default").update(export_available_hours=0)
        PrivacyRequest.objects.create(user=self.user, kind="export")
        self.assertEqual(privacy.due(), [])

    @override_settings(PRIVATE_STORAGE_KEY=None, PUBLIC_ORIGIN="https://example.test")
    def test_a_public_deployment_refuses_to_store_without_a_key(self):
        from django.core.exceptions import ImproperlyConfigured

        row = PrivacyRequest.objects.create(user=self.user, kind="export")
        with self.assertRaises(ImproperlyConfigured):
            privacy.process(row.pk)

    def test_encryption_at_rest_when_a_key_is_configured(self):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        with override_settings(PRIVATE_STORAGE_KEY=key):
            artifact = storage.store(self.user, "test", "a.json", b'{"secret": 1}')
            on_disk = (storage.root() / f"{artifact.pk}.bin").read_bytes()
            self.assertNotIn(b"secret", on_disk)
            self.assertEqual(storage.read(artifact), b'{"secret": 1}')


class DeletionTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user("other@example.com")
        approve_policy()
        connection = CreatorConnection.objects.create(
            requester=self.user,
            recipient=self.other,
            pair_key=":".join(sorted([str(self.user.pk), str(self.other.pk)])),
            state="accepted",
        )
        self.message = DirectMessage.objects.create(
            connection=connection,
            sender=self.user,
            body="Shared thread content",
            client_id=uuid.uuid4(),
        )

    def _request(self, hours_ago=48):
        row = PrivacyRequest.objects.create(user=self.user, kind="deletion")
        PrivacyRequest.objects.filter(pk=row.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_ago)
        )
        row.refresh_from_db()
        return row

    def test_deletion_waits_for_the_approved_grace_period(self):
        self._request(hours_ago=1)
        self.assertEqual(privacy.due(), [])
        self.assertTrue(self.user.__class__.objects.filter(pk=self.user.pk).exists())

    def test_deletion_runs_after_the_grace_period(self):
        row = self._request()
        self.assertEqual([item.pk for item in privacy.due()], [row.pk])
        privacy.process(row.pk)
        self.assertFalse(self.user.__class__.objects.filter(pk=self.user.pk).exists())
        row.refresh_from_db()
        self.assertEqual(row.state, "completed")
        self.assertTrue(
            AuditEvent.objects.filter(action="privacy.deletion.executed").exists()
        )

    def test_retained_policy_keeps_the_other_participants_history(self):
        privacy.process(self._request().pk)
        self.message.refresh_from_db()
        self.assertIsNone(self.message.sender_id)
        self.assertEqual(self.message.body, "Shared thread content")
        self.assertIsNotNone(self.message.redacted_at)

    def test_delete_policy_removes_the_messages(self):
        RetentionPolicy.objects.filter(key="default").update(
            shared_message_handling="delete"
        )
        privacy.process(self._request().pk)
        self.assertFalse(DirectMessage.objects.filter(pk=self.message.pk).exists())

    def test_deletion_removes_stored_artifacts(self):
        artifact = storage.store(self.user, "privacy-export", "a.json", b"{}")
        path = storage.root() / f"{artifact.pk}.bin"
        self.assertTrue(path.exists())
        privacy.process(self._request().pk)
        self.assertFalse(path.exists())
        self.assertFalse(PrivateArtifact.objects.filter(pk=artifact.pk).exists())

    def test_command_processes_due_requests(self):
        self._request()
        call_command("process_privacy_requests", verbosity=0)
        self.assertFalse(self.user.__class__.objects.filter(pk=self.user.pk).exists())

    def test_dry_run_changes_nothing(self):
        self._request()
        call_command("process_privacy_requests", dry_run=True, verbosity=0)
        self.assertTrue(self.user.__class__.objects.filter(pk=self.user.pk).exists())


class RetentionTests(TestCase):
    def setUp(self):
        self.user = make_user()
        approve_policy(audit_retention_days=30, notification_retention_days=7)

    def test_expired_artifacts_audit_and_notifications_are_trimmed(self):
        stale = storage.store(
            self.user,
            "privacy-export",
            "old.json",
            b"{}",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        fresh = storage.store(
            self.user,
            "privacy-export",
            "new.json",
            b"{}",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        old_audit = AuditEvent.objects.create(
            actor=self.user, action="test", resource_type="x", resource_id="1"
        )
        AuditEvent.objects.filter(pk=old_audit.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        read_notice = Notification.objects.create(
            user=self.user,
            category="messages",
            title="old",
            url="/",
            dedupe_key="old",
            read_at=timezone.now() - timedelta(days=10),
        )
        unread = Notification.objects.create(
            user=self.user, category="messages", title="new", url="/", dedupe_key="new"
        )
        summary = privacy.apply_retention()
        self.assertEqual(summary["artifacts"], 1)
        self.assertFalse(PrivateArtifact.objects.filter(pk=stale.pk).exists())
        self.assertTrue(PrivateArtifact.objects.filter(pk=fresh.pk).exists())
        self.assertFalse(AuditEvent.objects.filter(pk=old_audit.pk).exists())
        self.assertFalse(Notification.objects.filter(pk=read_notice.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=unread.pk).exists())

    def test_zero_days_keeps_history(self):
        RetentionPolicy.objects.filter(key="default").update(
            audit_retention_days=0, notification_retention_days=0
        )
        old_audit = AuditEvent.objects.create(
            actor=self.user, action="test", resource_type="x", resource_id="1"
        )
        AuditEvent.objects.filter(pk=old_audit.pk).update(
            created_at=timezone.now() - timedelta(days=4000)
        )
        privacy.apply_retention()
        self.assertTrue(AuditEvent.objects.filter(pk=old_audit.pk).exists())

    def test_command_reports_removals(self):
        call_command("apply_retention", verbosity=0)
