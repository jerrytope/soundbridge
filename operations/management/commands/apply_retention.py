from django.core.management.base import BaseCommand, CommandError
from operations import privacy


class Command(BaseCommand):
    help = (
        "Apply the approved retention policy: expire private artifacts and trim "
        "audit and notification history. Schedule hourly."
    )

    def handle(self, **options):
        try:
            summary = privacy.apply_retention()
        except privacy.PolicyRequired as problem:
            raise CommandError(str(problem))
        self.stdout.write(
            "Removed {artifacts} expired artifact(s), {audit} audit record(s), "
            "{notifications} read notification(s).".format(**summary)
        )
