"""Copy accounts, workspaces and images out of the Node server's database.

The Node server stored one row per account in `.data/soundbridge.sqlite`, with
the whole workspace as JSON on `users.workspace` and image bytes in `images`.
This command reads that file (read-only, never modified) and writes the same
data into the Django models.

Password hashes are carried across in the `salt:scrypt-hex` format Node wrote,
so imported accounts sign in with their existing password and are upgraded to
Django's default hasher on the next successful login. Image ids are preserved,
so the `/api/images/<id>` URLs already stored inside a workspace keep resolving.

Sessions are deliberately not imported: an imported account signs in again.

    python manage.py import_node_data                     # .data/soundbridge.sqlite
    python manage.py import_node_data --database path.db  # another file
    python manage.py import_node_data --dry-run           # report, write nothing
"""
import json
import sqlite3
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.hashers import from_node
from accounts.models import CreatorProfile, StoredImage, User
from apiv1.serializers import WorkspaceError, apply_workspace, validate_workspace
from network.models import Creator

DEFAULT_DATABASE = '.data/soundbridge.sqlite'


class Command(BaseCommand):
    help = "Import accounts, workspaces and images from the Node server's SQLite database."

    def add_arguments(self, parser):
        parser.add_argument('--database', default=DEFAULT_DATABASE, help='Path to the Node SQLite file.')
        parser.add_argument('--dry-run', action='store_true', help='Report what would be imported.')

    def handle(self, *args, **options):
        path = options['database']
        dry_run = options['dry_run']
        try:
            source = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        except sqlite3.OperationalError as problem:
            raise CommandError(f'Could not open {path}: {problem}')
        source.row_factory = sqlite3.Row

        if not Creator.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    'No sample creators are seeded, so saved creators will not be imported. '
                    'Run "python manage.py seed_creators" first.'
                )
            )

        imported = skipped = images_copied = 0
        for row in source.execute('SELECT id, email, password, workspace, revision FROM users'):
            email = (row['email'] or '').strip().lower()
            if not email:
                self.stdout.write(self.style.WARNING('Skipped a row with no email address.'))
                skipped += 1
                continue
            if User.objects.filter(email=email).exists():
                self.stdout.write(f'{email}: already present, left untouched.')
                skipped += 1
                continue
            if dry_run:
                workspace_size = len(row['workspace'] or '')
                image_count = source.execute(
                    'SELECT COUNT(*) FROM images WHERE user_id=?', (row['id'],)
                ).fetchone()[0]
                self.stdout.write(
                    f'{email}: would import (workspace {workspace_size} bytes, {image_count} images).'
                )
                imported += 1
                continue
            copied = self._import_account(source, row, email)
            images_copied += copied
            imported += 1

        source.close()
        verb = 'Would import' if dry_run else 'Imported'
        self.stdout.write(
            self.style.SUCCESS(f'{verb} {imported} account(s), copied {images_copied} image(s), skipped {skipped}.')
        )

    @transaction.atomic
    def _import_account(self, source, row, email):
        user = User(
            id=_uuid(row['id']),
            email=email,
            password=from_node(row['password'] or ''),
            workspace_revision=row['revision'] or 0,
        )
        user.save()
        CreatorProfile.objects.create(user=user)

        images = 0
        for image in source.execute('SELECT id, bytes FROM images WHERE user_id=?', (row['id'],)):
            data = bytes(image['bytes'])
            StoredImage.objects.create(
                id=_uuid(image['id']), user=user, bytes=data, byte_size=len(data)
            )
            images += 1

        owned = {stored.url for stored in StoredImage.objects.filter(user=user)}
        try:
            state = json.loads(row['workspace'] or '{}')
            validated = validate_workspace(state, email, lambda url: url in owned)
        except (ValueError, WorkspaceError) as problem:
            self.stdout.write(
                self.style.WARNING(
                    f'{email}: account and {images} image(s) imported, but the workspace was not '
                    f'readable and was left empty ({problem}).'
                )
            )
            return images

        apply_workspace(user, validated)
        self.stdout.write(f'{email}: imported with {images} image(s).')
        return images


def _uuid(value):
    """Keep the original identifier when it is a UUID, so stored URLs still resolve."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return uuid.uuid4()
