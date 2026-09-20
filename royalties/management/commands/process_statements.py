from django.core.management.base import BaseCommand
from royalties.models import ImportBatch
from royalties.imports import process


class Command(BaseCommand):
    help = "Scan and parse quarantined statements with bounded isolated processing."

    def handle(self, **options):
        for pk in ImportBatch.objects.filter(state="quarantined").values_list(
            "pk", flat=True
        )[:20]:
            process(pk)
