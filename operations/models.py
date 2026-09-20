"""Audited operations and durable delivery; private contents never enter audit metadata."""

import uuid
from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=80)
    resource_type = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class NotificationPreference(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.CharField(max_length=40)
    email = models.BooleanField(default=False)
    in_app = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category"], name="notification_preference"
            )
        ]


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    category = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    url = models.CharField(max_length=300)
    dedupe_key = models.CharField(max_length=200, unique=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EmailDelivery(models.Model):
    """Outbox rows survive a worker restart; a send/commit crash may resend email.

    A message that exhausts its retries is marked failed with the error class
    that stopped it, so an operator can see delivery problems instead of losing
    them. Message text is never recorded in the failure.
    """

    MAX_ATTEMPTS = 8

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    dedupe_key = models.CharField(max_length=200, unique=True)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(
        max_length=200, blank=True, help_text="Error type only, never message content."
    )

    @property
    def state(self):
        if self.sent_at:
            return "sent"
        if self.failed_at:
            return "failed"
        return "queued"


class PrivacyRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="privacy_requests",
    )
    kind = models.CharField(
        max_length=20, choices=[("export", "Export"), ("deletion", "Account deletion")]
    )
    state = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class LaunchDecision(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    decision = models.TextField()
    owner = models.CharField(max_length=200)
    approved_at = models.DateTimeField(null=True, blank=True)


class MutationReceipt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    payload = models.JSONField()
    status = models.PositiveSmallIntegerField(default=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "key"], name="api_mutation_receipt")
        ]


class RetentionPolicy(models.Model):
    """Operator-approved retention and deletion rules.

    Every value here is a commercial or legal decision, so the model ships with
    no meaningful defaults and nothing reads it until an owner has approved it.
    Deletion processing refuses to run while `approved_at` is empty, which keeps
    the PRD rule that policy decisions are not invented in code.
    """

    SHARED_CHOICES = [
        ("", "Not decided"),
        ("delete", "Delete messages this account sent"),
        ("retain_anonymised", "Keep the text, remove the sender identity"),
    ]

    key = models.SlugField(max_length=40, unique=True, default="default")
    deletion_grace_hours = models.PositiveIntegerField(
        default=0, help_text="Hours between a deletion request and its execution."
    )
    shared_message_handling = models.CharField(
        max_length=20, choices=SHARED_CHOICES, blank=True, default=""
    )
    export_available_hours = models.PositiveIntegerField(
        default=0, help_text="How long a generated export stays downloadable. 0 disables exports."
    )
    audit_retention_days = models.PositiveIntegerField(
        default=0, help_text="Days to keep audit records. 0 keeps them indefinitely."
    )
    notification_retention_days = models.PositiveIntegerField(
        default=0, help_text="Days to keep read in-app notifications. 0 keeps them."
    )
    decision_reference = models.CharField(
        max_length=200,
        blank=True,
        help_text="The approved LaunchDecision or document this policy comes from.",
    )
    owner = models.CharField(max_length=200, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [("approve_retentionpolicy", "Can approve retention policy")]
        verbose_name_plural = "Retention policies"

    def __str__(self):
        return f"Retention policy ({'approved' if self.approved else 'draft'})"

    @property
    def approved(self):
        return bool(
            self.approved_at
            and self.owner.strip()
            and self.shared_message_handling
            and self.decision_reference.strip()
        )


class PrivateArtifact(models.Model):
    """A private file held outside the database for one account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="artifacts"
    )
    kind = models.CharField(max_length=40)
    filename = models.CharField(max_length=200)
    content_type = models.CharField(max_length=100, default="application/json")
    byte_size = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    encrypted = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["expires_at"])]
