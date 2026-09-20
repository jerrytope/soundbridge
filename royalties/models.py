"""Royalty estimates, statements and normalised transactions.

Replaces the `calculations`, `statements` and `royaltySources` arrays. Every
monetary column is Decimal with an explicit currency, and no amount is ever
converted between currencies (PRD 10.2, 10.3 and 12.3).
"""

import uuid

from django.conf import settings
from django.db import models

CURRENCIES = [("USD", "USD"), ("NGN", "NGN"), ("EUR", "EUR"), ("GBP", "GBP")]

SOURCES = [
    "Spotify",
    "Apple Music",
    "Boomplay",
    "Audiomack",
    "YouTube Music",
    "Amazon Music",
    "Other",
]

# Royalty categories the product explains (PRD 10.1). Statements map onto these;
# the estimator covers master recording income only and says so on the page.
CATEGORIES = [
    ("master", "Master recording"),
    ("mechanical", "Mechanical"),
    ("performance", "Performance"),
    ("neighbouring", "Neighbouring rights"),
    ("sync", "Synchronisation"),
    ("producer", "Producer or featured artist share"),
    ("direct", "Direct sales and licensing"),
]


class IncomeSource(models.Model):
    """A royalty source the creator selected. Selecting one connects nothing."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="royalty_sources",
    )
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_user_source")
        ]
        ordering = ["id"]

    def __str__(self):
        return self.name


class Calculation(models.Model):
    """A saved scenario, not a payout forecast.

    The rate is supplied by the creator from their own statement or agreement,
    so the stored rate source records that provenance rather than implying a
    platform-published rate (PRD 10.2).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calculations"
    )
    platform = models.CharField(max_length=300)
    streams = models.BigIntegerField()
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    share = models.DecimalField(max_digits=7, decimal_places=4)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="USD")
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    category = models.CharField(max_length=20, choices=CATEGORIES, default="master")
    rate_source = models.CharField(max_length=200, default="creator-supplied")
    rate_effective_date = models.DateField(null=True, blank=True)
    rate_version = models.CharField(max_length=40, default="user-1")
    formula = models.CharField(max_length=200, default="streams * rate * share / 100")
    assumptions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.platform} · {self.amount} {self.currency}"


class Statement(models.Model):
    """An imported royalty statement. The original upload is retained for traceability."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    STATES = [(PENDING, "Pending"), (PROCESSED, "Processed"), (FAILED, "Failed")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="statements"
    )
    name = models.CharField(max_length=300)
    source = models.CharField(max_length=120, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    original_csv = models.BinaryField(null=True, blank=True)
    # Set once the original upload has been moved into private storage.
    original_artifact = models.ForeignKey(
        "operations.PrivateArtifact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="statements",
    )
    schema_version = models.CharField(max_length=20, default="csv-1")
    processing_state = models.CharField(
        max_length=20, choices=STATES, default=PROCESSED
    )
    row_fingerprint = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.name

    def original_bytes(self):
        """The uploaded CSV, wherever it is held. None when it was not kept."""
        if self.original_artifact_id:
            from operations import storage

            return storage.read(self.original_artifact)
        return bytes(self.original_csv) if self.original_csv else None

    def totals(self):
        """Per-currency totals; currencies are never silently combined."""
        result = {}
        for row in self.transactions.all():
            result[row.currency] = result.get(row.currency, 0) + row.amount
        return result


class RoyaltyTransaction(models.Model):
    """One statement line mapped onto the canonical schema (PRD 10.3).

    `track`, `platform`, `amount` and `currency` come from the four required CSV
    columns; the remaining fields stay null until a source provides them, rather
        than being guessed.
    """

    statement = models.ForeignKey(
        Statement, on_delete=models.CASCADE, related_name="transactions"
    )
    position = models.IntegerField(default=0)
    track = models.CharField(max_length=500)
    platform = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=3, choices=CURRENCIES)
    work = models.CharField(max_length=500, blank=True)
    recording_id = models.CharField(max_length=120, blank=True)
    territory = models.CharField(max_length=120, blank=True)
    usage_type = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORIES, blank=True)
    units = models.BigIntegerField(null=True, blank=True)
    gross_amount = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    deductions = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    net_amount = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    payee = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["position", "id"]
        indexes = [models.Index(fields=["statement", "position"])]


class ManualIncome(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="manual_income"
    )
    source = models.CharField(max_length=200)
    work = models.CharField(max_length=500, blank=True)
    platform = models.CharField(max_length=200, blank=True)
    territory = models.CharField(max_length=120, blank=True)
    date = models.DateField()
    category = models.CharField(max_length=20, choices=CATEGORIES)
    currency = models.CharField(max_length=3, choices=CURRENCIES)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    note = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="import_batches",
    )
    name = models.CharField(max_length=300)
    raw = models.BinaryField()
    digest = models.CharField(max_length=64)
    state = models.CharField(
        max_length=20,
        default="quarantined",
        choices=[
            ("quarantined", "Waiting for scan"),
            ("review", "Mapping review"),
            ("imported", "Imported"),
            ("failed", "Failed"),
        ],
    )
    error = models.CharField(max_length=500, blank=True)
    columns = models.JSONField(default=list)
    extracted_rows = models.JSONField(default=list)
    mapping = models.JSONField(default=dict)
    statement = models.OneToOneField(
        Statement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="import_batch",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "digest"], name="unique_import_content"
            )
        ]


class MappingRevision(models.Model):
    batch = models.ForeignKey(
        ImportBatch, on_delete=models.CASCADE, related_name="revisions"
    )
    mapping = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
