"""Password-hash compatibility and the Node data import."""
import hashlib
import json
import sqlite3
import uuid
from io import BytesIO

from django.contrib.auth import authenticate
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image as PilImage

from accounts.hashers import NodeScryptPasswordHasher, from_node
from accounts.models import CreatorProfile, StoredImage, User

PASSWORD = 'correcthorsebattery1'


def node_hash(password, salt='a1b2c3d4e5f60718'):
    """Produce the `salt:hex` value the Node server wrote, using Node's scrypt defaults."""
    digest = hashlib.scrypt(
        password.encode('utf-8'), salt=salt.encode('utf-8'), n=16384, r=8, p=1, dklen=64,
        maxmem=64 * 1024 * 1024,
    ).hex()
    return f'{salt}:{digest}'


@override_settings(
    PASSWORD_HASHERS=[
        'django.contrib.auth.hashers.PBKDF2PasswordHasher',
        'accounts.hashers.NodeScryptPasswordHasher',
    ]
)
class NodeHasherTests(TestCase):
    def test_an_account_created_by_the_node_server_can_sign_in(self):
        user = User(email='old@example.com', password=from_node(node_hash(PASSWORD)))
        user.save()
        CreatorProfile.objects.create(user=user)
        self.assertIsNotNone(authenticate(None, email='old@example.com', password=PASSWORD))

    def test_a_wrong_password_is_still_refused(self):
        user = User(email='old@example.com', password=from_node(node_hash(PASSWORD)))
        user.save()
        CreatorProfile.objects.create(user=user)
        self.assertIsNone(authenticate(None, email='old@example.com', password='another-password'))

    def test_the_hash_is_upgraded_on_a_successful_login(self):
        user = User(email='old@example.com', password=from_node(node_hash(PASSWORD)))
        user.save()
        CreatorProfile.objects.create(user=user)
        self.assertTrue(user.password.startswith(NodeScryptPasswordHasher.algorithm))
        authenticate(None, email='old@example.com', password=PASSWORD)
        user.refresh_from_db()
        self.assertTrue(user.password.startswith('pbkdf2_'))


def _png():
    buffer = BytesIO()
    PilImage.new('RGB', (40, 40), (10, 20, 30)).save(buffer, format='PNG')
    return buffer.getvalue()


def build_node_database(path, email='old@example.com', workspace=None, image_id=None):
    """Write a database shaped like the one server/database.js created."""
    image_id = image_id or str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    workspace = workspace or {
        'profile': {
            'name': 'Old Creator',
            'photo': f'/api/images/{image_id}',
            'email': email,
            'role': 'Producer',
            'city': 'Lagos',
            'bio': 'Imported from the Node server.',
            'genres': ['Afrobeats'],
            'goals': ['Plan a release'],
        },
        'connections': [],
        'projects': [],
        'applications': [],
        'releases': [
            {
                'id': str(uuid.uuid4()),
                'title': 'Night Drive',
                'type': 'Single',
                'date': '2026-11-20',
                'artwork': '',
                'tasks': [{'id': str(uuid.uuid4()), 'title': 'Master', 'done': True}],
            }
        ],
        'statements': [],
        'calculations': [],
        'drafts': [],
        'aiConversations': [],
        'aiDeliverables': [],
        'royaltySources': ['Spotify'],
    }
    db = sqlite3.connect(path)
    db.executescript(
        'CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,'
        ' workspace TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0);'
        'CREATE TABLE images (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, bytes BLOB NOT NULL);'
        'CREATE TABLE sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires INTEGER NOT NULL);'
    )
    db.execute(
        'INSERT INTO users VALUES (?,?,?,?,?)',
        (user_id, email, node_hash(PASSWORD), json.dumps(workspace), 7),
    )
    db.execute('INSERT INTO images VALUES (?,?,?)', (image_id, user_id, _png()))
    db.commit()
    db.close()
    return {'user_id': user_id, 'image_id': image_id, 'workspace': workspace}


class ImportNodeDataTests(TestCase):
    def setUp(self):
        from network.management.commands.seed_creators import Command as Seed

        Seed().handle()
        self.path = self._path()

    def _path(self):
        import tempfile
        from pathlib import Path

        directory = tempfile.mkdtemp()
        return str(Path(directory) / 'soundbridge.sqlite')

    def test_imports_account_profile_release_and_image(self):
        details = build_node_database(self.path)
        call_command('import_node_data', database=self.path, verbosity=0)
        user = User.objects.get(email='old@example.com')
        self.assertEqual(user.workspace_revision, 7)
        self.assertEqual(user.profile.name, 'Old Creator')
        self.assertEqual(user.profile.genres, ['Afrobeats'])
        self.assertEqual(user.releases.get().title, 'Night Drive')
        self.assertTrue(user.releases.get().tasks.get().done)
        self.assertEqual(user.royalty_sources.get().name, 'Spotify')
        self.assertEqual(str(StoredImage.objects.get(user=user).id), details['image_id'])

    def test_image_ids_are_preserved_so_stored_urls_resolve(self):
        details = build_node_database(self.path)
        call_command('import_node_data', database=self.path, verbosity=0)
        user = User.objects.get(email='old@example.com')
        self.assertEqual(user.profile.photo, f'/api/images/{details["image_id"]}')
        self.client.force_login(user)
        response = self.client.get(user.profile.photo)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')

    @override_settings(
        PASSWORD_HASHERS=[
            'django.contrib.auth.hashers.PBKDF2PasswordHasher',
            'accounts.hashers.NodeScryptPasswordHasher',
        ]
    )
    def test_imported_account_signs_in_with_its_original_password(self):
        build_node_database(self.path)
        call_command('import_node_data', database=self.path, verbosity=0)
        self.assertIsNotNone(authenticate(None, email='old@example.com', password=PASSWORD))

    def test_dry_run_writes_nothing(self):
        build_node_database(self.path)
        call_command('import_node_data', database=self.path, dry_run=True, verbosity=0)
        self.assertFalse(User.objects.filter(email='old@example.com').exists())

    def test_existing_account_is_left_untouched(self):
        build_node_database(self.path)
        existing = User.objects.create_user(email='old@example.com', password=PASSWORD, name='Mine')
        call_command('import_node_data', database=self.path, verbosity=0)
        existing.refresh_from_db()
        self.assertEqual(existing.profile.name, 'Mine')
        self.assertEqual(User.objects.filter(email='old@example.com').count(), 1)

    def test_an_unreadable_workspace_still_imports_the_account(self):
        build_node_database(self.path)
        db = sqlite3.connect(self.path)
        db.execute('UPDATE users SET workspace=?', ('{not json',))
        db.commit()
        db.close()
        call_command('import_node_data', database=self.path, verbosity=0)
        user = User.objects.get(email='old@example.com')
        self.assertEqual(user.profile.name, '')
        self.assertEqual(StoredImage.objects.filter(user=user).count(), 1)

    def test_missing_database_reports_clearly(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command('import_node_data', database=self.path + '.nope', verbosity=0)
