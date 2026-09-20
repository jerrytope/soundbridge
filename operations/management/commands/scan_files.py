from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from network.models import CollaborationFile
from royalties.imports import scan


class Command(BaseCommand):
    help = (
        "Scan quarantined collaboration files; scanner failures never expose content."
    )

    def handle(self, **options):
        for item in CollaborationFile.objects.filter(state="quarantined")[:20]:
            try:
                scan(bytes(item.content))
            except ValidationError as error:
                if error.code == "infected":
                    CollaborationFile.objects.filter(
                        pk=item.pk, state="quarantined"
                    ).update(state="rejected")
                continue
            CollaborationFile.objects.filter(pk=item.pk, state="quarantined").update(
                state="clean"
            )
