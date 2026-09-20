"""Move private bytes out of database columns into the private artifact store."""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import StoredImage
from operations import storage
from royalties.models import Statement


class Command(BaseCommand):
    help = (
        "Move stored images and original statement uploads into private storage, "
        "which encrypts them at rest when a key is configured. Safe to re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Report what would move."
        )
        parser.add_argument(
            "--batch", type=int, default=200, help="Rows to move per model per run."
        )

    def handle(self, **options):
        dry_run = options["dry_run"]
        batch = options["batch"]
        images = StoredImage.objects.filter(artifact__isnull=True).exclude(bytes=None)[:batch]
        statements = Statement.objects.filter(original_artifact__isnull=True).exclude(
            original_csv=None
        )[:batch]
        if dry_run:
            self.stdout.write(
                f"Would move {images.count()} image(s) and {statements.count()} statement upload(s)."
            )
            return
        moved_images = 0
        for image in list(images):
            data = bytes(image.bytes or b"")
            if not data:
                continue
            with transaction.atomic():
                artifact = storage.store(
                    image.user,
                    kind="profile-image",
                    filename=f"{image.pk}.jpg",
                    data=data,
                    content_type="image/jpeg",
                )
                StoredImage.objects.filter(pk=image.pk).update(
                    artifact=artifact, bytes=None, byte_size=len(data)
                )
            moved_images += 1
        moved_statements = 0
        for statement in list(statements):
            data = bytes(statement.original_csv or b"")
            if not data:
                continue
            with transaction.atomic():
                artifact = storage.store(
                    statement.owner,
                    kind="statement-original",
                    filename=f"{statement.pk}.csv",
                    data=data,
                    content_type="text/csv",
                )
                Statement.objects.filter(pk=statement.pk).update(
                    original_artifact=artifact, original_csv=None
                )
            moved_statements += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Moved {moved_images} image(s) and {moved_statements} statement upload(s) "
                "into private storage."
            )
        )
