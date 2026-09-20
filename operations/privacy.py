"""Processing for the privacy requests people make about their own data.

Two requests can be made: an export of everything the account owns, and
deletion of the account. Both are carried out here rather than in a view, so a
worker can run them, so they are audited, and so deletion waits out the grace
period the operator approved.

Nothing runs until a `RetentionPolicy` has been approved by a named owner and
references the decision it comes from. Grace periods, how long an export stays
downloadable, and what happens to messages this account sent into someone
else's thread are all policy, so they are read from that record and never
guessed here.
"""

import json
from datetime import timedelta

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from operations import storage
from operations.models import (
    AuditEvent,
    Notification,
    PrivacyRequest,
    RetentionPolicy,
)
from operations.services import audit, notify


class PolicyRequired(RuntimeError):
    """Raised when a request cannot proceed because no policy is approved."""


def policy():
    """The approved retention policy, or None when the operator has not set one."""
    row = RetentionPolicy.objects.filter(key="default").first()
    return row if row and row.approved else None


def _require_policy():
    current = policy()
    if current is None:
        raise PolicyRequired(
            "No approved retention policy. Approve one in the admin before privacy "
            "requests can be processed."
        )
    return current


def due(now=None):
    """Requests that are ready to be processed under the approved policy."""
    current = _require_policy()
    now = now or timezone.now()
    exports = PrivacyRequest.objects.filter(kind="export", state="pending")
    deletions = PrivacyRequest.objects.filter(
        kind="deletion",
        state="pending",
        created_at__lte=now - timedelta(hours=current.deletion_grace_hours),
    )
    if current.export_available_hours == 0:
        exports = exports.none()
    return list(exports) + list(deletions)


def process(request_id):
    """Run one privacy request. Returns the request in its new state."""
    current = _require_policy()
    row = PrivacyRequest.objects.select_related("user").get(pk=request_id)
    if row.state != "pending" or row.user is None:
        return row
    row.state = "processing"
    row.save(update_fields=["state"])
    if row.kind == "export":
        return _export(row, current)
    return _delete(row, current)


def _export(row, current):
    from operations.views import workspace_export

    user = row.user
    payload = json.dumps(workspace_export(user), cls=DjangoJSONEncoder, indent=2)
    artifact = storage.store(
        user,
        kind="privacy-export",
        filename="soundbridge-export.json",
        data=payload.encode("utf-8"),
        expires_at=timezone.now() + timedelta(hours=current.export_available_hours),
    )
    row.state = "completed"
    row.completed_at = timezone.now()
    row.save(update_fields=["state", "completed_at"])
    audit(user, "privacy.export.completed", row)
    notify(
        user,
        "privacy",
        "Your data export is ready",
        "/settings/privacy",
        f"export:{row.pk}",
    )
    return row


def _delete(row, current):
    """Delete the account, handling shared content the way the policy says."""
    user = row.user
    identifier = str(user.pk)
    _handle_shared_messages(user, current)
    with transaction.atomic():
        AuditEvent.objects.create(
            actor=None,
            action="privacy.deletion.executed",
            resource_type="accounts.user",
            resource_id=identifier,
        )
        for artifact in user.artifacts.all():
            storage.discard(artifact)
        user.delete()
        # The request row outlives the account with its user set to NULL, so it
        # is updated by query rather than through the now-detached instance.
        PrivacyRequest.objects.filter(pk=row.pk).update(
            state="completed", completed_at=timezone.now()
        )
    row.refresh_from_db()
    return row


def _handle_shared_messages(user, current):
    """Direct messages sit in another person's thread, so the policy decides."""
    from network.models import DirectMessage

    if current.shared_message_handling == "retain_anonymised":
        DirectMessage.objects.filter(sender=user).update(
            sender=None, redacted_at=timezone.now()
        )
    else:
        DirectMessage.objects.filter(sender=user).delete()


def apply_retention(now=None):
    """Housekeeping the approved policy asks for. Returns a summary of removals."""
    current = _require_policy()
    now = now or timezone.now()
    summary = {"artifacts": storage.purge_expired(now), "audit": 0, "notifications": 0}
    if current.audit_retention_days:
        cutoff = now - timedelta(days=current.audit_retention_days)
        summary["audit"] = AuditEvent.objects.filter(created_at__lt=cutoff).delete()[0]
    if current.notification_retention_days:
        cutoff = now - timedelta(days=current.notification_retention_days)
        summary["notifications"] = Notification.objects.filter(
            read_at__isnull=False, read_at__lt=cutoff
        ).delete()[0]
    return summary
