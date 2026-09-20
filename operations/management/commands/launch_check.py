"""Fail closed until the release gates are satisfied.

The gates fall into two kinds. Configuration and approval gates are checked
against the database and the settings. Evidence gates are decisions and
verification an operator records; code cannot certify them, so their absence is
reported rather than assumed.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from operations.models import LaunchDecision

DECISIONS = [
    "launch-markets",
    "legal-entity",
    "terms-copy",
    "privacy-copy",
    "email-provider",
    "payment-provider",
    "plan-prices-and-limits",
    "cancellation-and-refunds",
    "retention-and-deletion",
    "ai-processing-and-escalation",
    "moderation-owner",
    "royalty-formats-and-rates",
    "reviewed-education",
    "hosting-encryption",
    "backup-restore-evidence",
    "browser-accessibility-evidence",
    "security-load-evidence",
    "ai-evaluation-evidence",
    "support-and-incident-owners",
]


class Command(BaseCommand):
    help = "Fail closed until required decisions, evidence and release gates are satisfied."

    def handle(self, **options):
        blockers = []
        blockers += self._decisions()
        blockers += self._configuration()
        blockers += self._implementation()
        for item in blockers:
            self.stdout.write("BLOCKED: " + item)
        if blockers:
            raise CommandError(
                f"{len(blockers)} release gates remain. This build is not launch-certified."
            )
        self.stdout.write(
            self.style.SUCCESS(
                "All recorded gates are satisfied. Launch remains a human decision."
            )
        )

    def _decisions(self):
        approved = set(
            LaunchDecision.objects.filter(approved_at__isnull=False)
            .exclude(owner="")
            .exclude(decision="")
            .values_list("key", flat=True)
        )
        return [
            "Missing approved decision/evidence: " + key
            for key in DECISIONS
            if key not in approved
        ]

    def _configuration(self):
        blockers = []
        if not settings.PUBLIC_ORIGIN:
            blockers.append("Public HTTPS origin is not configured.")
        if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.mysql":
            blockers.append("Production MySQL is not configured.")
        if not settings.REQUIRE_EMAIL_VERIFICATION:
            blockers.append(
                "Email verification is switched off, so an address is never proven to "
                "belong to the person who typed it. Password recovery then sends a "
                "reset link to an unproven address. Set "
                "SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION=true, or record the decision "
                "to accept this and delete this check."
            )
        if not settings.MALWARE_SCANNER:
            blockers.append("Malware scanner is not configured.")
        if "console" in settings.EMAIL_BACKEND:
            blockers.append("Email still uses the development console backend.")
        if not settings.PRIVATE_STORAGE_KEY:
            blockers.append(
                "Private artifact encryption key is not configured "
                "(SOUNDBRIDGE_PRIVATE_STORAGE_KEY)."
            )
        if not settings.MODERATION_MODEL:
            blockers.append(
                "AI moderation model is not configured (SOUNDBRIDGE_MODERATION_MODEL)."
            )
        return blockers

    def _implementation(self):
        """Gates that depend on records the application itself can check."""
        from billing.models import Plan
        from billing.providers import configured as billing_configured
        from operations.privacy import policy

        blockers = []
        if not billing_configured():
            blockers.append(
                "No payment provider adapter is configured. The checkout, webhook and "
                "reconciliation paths are implemented; select a provider and implement "
                "billing.providers.Provider for it."
            )
        if not Plan.objects.filter(approved_at__isnull=False).exists():
            blockers.append("No approved commercial plan exists, so entitlements are closed.")
        if policy() is None:
            blockers.append(
                "No approved retention policy, so exports, deletion and retention "
                "processing will not run."
            )
        blockers += self._evaluation_evidence()
        blockers += self._storage_gap()
        return blockers

    def _evaluation_evidence(self):
        from aiteam.models import EvaluationRun

        run = EvaluationRun.objects.first()
        if run is None:
            return ["No AI evaluation run recorded. Run: manage.py run_ai_evaluations."]
        if run.failed:
            return [
                f"The most recent AI evaluation run has {run.failed} failing case(s)."
            ]
        if run.model != (settings.OPENAI_MODEL or ""):
            return [
                "The most recent AI evaluation ran against a different model than the "
                "one configured now."
            ]
        return []

    def _storage_gap(self):
        """Private bytes that still live in database columns."""
        from accounts.models import StoredImage
        from royalties.models import Statement

        # Only rows whose bytes are still in a column count; migrated rows keep
        # their row and point at an artifact.
        pending = (
            StoredImage.objects.exclude(bytes=None).count()
            + Statement.objects.exclude(original_csv=None).count()
        )
        if pending:
            return [
                f"{pending} private file(s) are still stored in database columns. "
                "Move them with: manage.py migrate_private_bytes."
            ]
        return []
