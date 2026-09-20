from zoneinfo import ZoneInfo
from django.core.management.base import BaseCommand
from django.utils import timezone
from releases.models import ReleaseTask
from network.models import SavedOpportunity
from operations.services import notify


class Command(BaseCommand):
    help = "Emit idempotent due-task and saved-opportunity reminders in each account timezone."

    def handle(self, **options):
        now = timezone.now()
        for task in ReleaseTask.objects.filter(
            done=False, due_date__isnull=False, release__reminders_enabled=True
        ).select_related("release__owner"):
            owner = task.release.owner
            local = now.astimezone(ZoneInfo(owner.timezone))
            if task.due_date <= local.date() and local.hour >= 9:
                notify(
                    owner,
                    "releases",
                    f"Release task due: {task.title[:150]}",
                    f"/releases/{task.release_id}",
                    f"release-task:{task.pk}:{task.due_date}",
                )
        for saved in SavedOpportunity.objects.filter(
            opportunity__is_sample=False,
            opportunity__verification_state="verified",
            opportunity__deadline__isnull=False,
        ).select_related("user", "opportunity"):
            local = now.astimezone(ZoneInfo(saved.user.timezone))
            days = (saved.opportunity.deadline - local.date()).days
            if days in (0, 1) and local.hour >= 9:
                notify(
                    saved.user,
                    "opportunities",
                    "Saved opportunity deadline approaching",
                    "/opportunities?saved=1",
                    f"opportunity:{saved.pk}:{saved.opportunity.deadline}:{days}",
                )
