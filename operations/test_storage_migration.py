"""Moving private bytes out of database columns.

The move has to be invisible to everything that reads those bytes: the image
still serves, the export still contains it, and running the command twice does
not duplicate or lose anything.
"""

import base64
from io import BytesIO

from cryptography.fernet import Fernet
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image as PilImage

from accounts.models import StoredImage
from apiv1.tests import make_user
from operations.models import PrivateArtifact
from operations.views import workspace_export
from royalties.models import Statement

CSV = b"track,platform,amount,currency\nA,Spotify,1.00,USD\n"


def png():
    buffer = BytesIO()
    PilImage.new("RGB", (32, 32), (90, 30, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


class MigratePrivateBytesTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.image = StoredImage.objects.create(
            user=self.user, bytes=png(), byte_size=len(png())
        )
        self.statement = Statement.objects.create(
            owner=self.user, name="statement.csv", original_csv=CSV
        )

    def test_dry_run_moves_nothing(self):
        call_command("migrate_private_bytes", dry_run=True, verbosity=0)
        self.image.refresh_from_db()
        self.assertIsNone(self.image.artifact_id)
        self.assertEqual(PrivateArtifact.objects.count(), 0)

    def test_bytes_move_and_stay_readable(self):
        call_command("migrate_private_bytes", verbosity=0)
        self.image.refresh_from_db()
        self.statement.refresh_from_db()
        self.assertIsNotNone(self.image.artifact_id)
        self.assertIsNone(self.image.bytes)
        self.assertEqual(self.image.data(), png())
        self.assertIsNotNone(self.statement.original_artifact_id)
        self.assertIsNone(self.statement.original_csv)
        self.assertEqual(self.statement.original_bytes(), CSV)

    def test_the_image_still_serves_after_the_move(self):
        call_command("migrate_private_bytes", verbosity=0)
        self.client.force_login(self.user)
        response = self.client.get(f"/api/images/{self.image.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, png())

    def test_the_export_still_contains_the_bytes(self):
        call_command("migrate_private_bytes", verbosity=0)
        payload = workspace_export(self.user)
        self.assertEqual(base64.b64decode(payload["images"][0]["base64"]), png())
        self.assertEqual(
            base64.b64decode(payload["statement_originals"][0]["base64"]), CSV
        )

    def test_running_twice_changes_nothing_further(self):
        call_command("migrate_private_bytes", verbosity=0)
        call_command("migrate_private_bytes", verbosity=0)
        self.assertEqual(PrivateArtifact.objects.count(), 2)

    def test_moved_bytes_are_encrypted_when_a_key_is_configured(self):
        from operations import storage

        with override_settings(PRIVATE_STORAGE_KEY=Fernet.generate_key().decode()):
            call_command("migrate_private_bytes", verbosity=0)
            self.image.refresh_from_db()
            on_disk = (storage.root() / f"{self.image.artifact_id}.bin").read_bytes()
            self.assertNotEqual(on_disk, png())
            self.assertEqual(self.image.data(), png())

    def test_another_account_still_cannot_read_the_image(self):
        call_command("migrate_private_bytes", verbosity=0)
        self.client.force_login(make_user("other@example.com"))
        self.assertEqual(
            self.client.get(f"/api/images/{self.image.pk}").status_code, 404
        )
