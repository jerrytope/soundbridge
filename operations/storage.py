"""Private artifact storage with expiring, authorized downloads.

Bytes that belong to one account — data exports today, and any other private
file that outgrows a database column — are written outside the database to a
private directory that is never served by the static or media handlers. Each
file is addressed by an opaque identifier, readable only through a view that
checks the owner and a signed link that expires.

Encryption at rest is real when `SOUNDBRIDGE_PRIVATE_STORAGE_KEY` holds a
Fernet key: the bytes on disk are ciphertext and the key lives in the process
environment, not in the repository. A deployment with a public origin must
configure the key; storing a private artifact without one fails closed rather
than writing plaintext to a server we have not been told is encrypted.

    key = Fernet.generate_key().decode()      # put this in the environment
"""

import hashlib
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

SALT = "soundbridge.private-artifact"


def root():
    path = Path(settings.PRIVATE_STORAGE_ROOT)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def _fernet():
    key = settings.PRIVATE_STORAGE_KEY
    if not key:
        if settings.PUBLIC_ORIGIN:
            raise ImproperlyConfigured(
                "SOUNDBRIDGE_PRIVATE_STORAGE_KEY is required before private artifacts "
                "can be stored on a public deployment."
            )
        return None
    from cryptography.fernet import Fernet

    return Fernet(key if isinstance(key, bytes) else key.encode())


def store(user, kind, filename, data, content_type="application/json", expires_at=None):
    """Write `data` for `user` and return the PrivateArtifact row describing it."""
    from operations.models import PrivateArtifact

    cipher = _fernet()
    artifact = PrivateArtifact(
        user=user,
        kind=kind,
        filename=filename,
        content_type=content_type,
        byte_size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        encrypted=cipher is not None,
        expires_at=expires_at,
    )
    path = root() / f"{artifact.pk}.bin"
    path.write_bytes(cipher.encrypt(data) if cipher else data)
    try:
        path.chmod(0o600)
    except OSError:
        # Windows and some network filesystems ignore POSIX modes; the directory
        # is still private and the artifact is only reachable through the view.
        pass
    artifact.save()
    return artifact


def read(artifact):
    path = root() / f"{artifact.pk}.bin"
    if not path.exists():
        raise FileNotFoundError("This file is no longer stored.")
    data = path.read_bytes()
    if not artifact.encrypted:
        return data
    cipher = _fernet()
    if cipher is None:
        raise ImproperlyConfigured(
            "This artifact was encrypted; configure SOUNDBRIDGE_PRIVATE_STORAGE_KEY to read it."
        )
    return cipher.decrypt(data)


def discard(artifact):
    """Remove the bytes and the row. Safe to call twice."""
    path = root() / f"{artifact.pk}.bin"
    path.unlink(missing_ok=True)
    artifact.delete()


def expired(artifact, now=None):
    now = now or timezone.now()
    return bool(artifact.expires_at and artifact.expires_at <= now)


def signed_url(artifact, ttl_seconds=900):
    """A link the owner can use for a short window, e.g. from an email."""
    token = TimestampSigner(salt=SALT).sign(str(artifact.pk))
    return f"/privacy/downloads/{artifact.pk}?token={token}&ttl={int(ttl_seconds)}"


def check_token(artifact, token, ttl_seconds):
    try:
        value = TimestampSigner(salt=SALT).unsign(token, max_age=int(ttl_seconds))
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        raise PermissionDenied("This download link is invalid or has expired.")
    if value != str(artifact.pk):
        raise PermissionDenied("This download link is for another file.")


def purge_expired(now=None):
    """Delete artifacts past their expiry. Returns how many were removed."""
    from operations.models import PrivateArtifact

    now = now or timezone.now()
    removed = 0
    for artifact in PrivateArtifact.objects.filter(
        expires_at__isnull=False, expires_at__lte=now
    ):
        discard(artifact)
        removed += 1
    return removed


def new_id():
    return uuid.uuid4()
