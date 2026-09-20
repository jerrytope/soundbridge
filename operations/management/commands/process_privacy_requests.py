from django.core.management.base import BaseCommand, CommandError
from operations import privacy


class Command(BaseCommand):
    help = (
        "Carry out pending data exports and account deletions under the approved "
        "retention policy. Schedule every few minutes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what is due without changing anything.",
        )

    def handle(self, **options):
        try:
            rows = privacy.due()
        except privacy.PolicyRequired as problem:
            raise CommandError(str(problem))
        if options["dry_run"]:
            for row in rows:
                self.stdout.write(f"due: {row.kind} {row.pk}")
            self.stdout.write(f"{len(rows)} request(s) due.")
            return
        done = 0
        for row in rows:
            result = privacy.process(row.pk)
            if result.state == "completed":
                done += 1
                self.stdout.write(f"completed: {result.kind} {result.pk}")
        self.stdout.write(self.style.SUCCESS(f"Processed {done} privacy request(s)."))
