from django.core.management.base import BaseCommand
from aiteam.evaluations import load_starter_cases


class Command(BaseCommand):
    help = "Create the starter AI evaluation cases that are missing."

    def handle(self, **options):
        created = load_starter_cases()
        self.stdout.write(
            self.style.SUCCESS(f"Added {created} evaluation case(s). Existing cases were kept.")
        )
