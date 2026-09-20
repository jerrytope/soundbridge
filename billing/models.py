from django.conf import settings
from django.db import models


class Plan(models.Model):
    code = models.SlugField(primary_key=True, max_length=20)
    name = models.CharField(max_length=100)
    limits = models.JSONField(
        default=dict,
        help_text="Approved nonnegative integer limits keyed by capability. Missing capabilities are disabled.",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    commercial_terms = models.TextField(blank=True)

    class Meta:
        permissions = [("approve_plan", "Can approve commercial plan configuration")]


class Subscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    provider = models.CharField(max_length=40)
    provider_reference = models.CharField(max_length=200, unique=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    state = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("past_due", "Past due"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
    )
    access_until = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)
    verified_at = models.DateTimeField()


class BillingEvent(models.Model):
    provider = models.CharField(max_length=40)
    provider_event_id = models.CharField(max_length=200)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_event_id"], name="billing_event_once"
            )
        ]
