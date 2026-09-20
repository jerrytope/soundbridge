"""Accounts, profiles and private image storage.

Replaces the `users`, `sessions` and `images` tables in server/database.js. The
workspace JSON blob that lived on `users.workspace` is gone: its contents are
modelled properly across the network, releases, royalties and aiteam apps, and
`workspace_revision` keeps the optimistic-locking contract the front end uses.
"""

import uuid

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

# Option lists ported verbatim from src/main.jsx so every choice grid offers
# exactly what the current UI offers.
ROLES = [
    "Artist",
    "Producer",
    "Songwriter",
    "Audio Engineer",
    "Music Manager",
    "Videographer",
    "Label",
    "Other",
]
GENRES = [
    "Afrobeats",
    "Amapiano",
    "R&B",
    "Hip-Hop",
    "Pop",
    "Gospel",
    "Alternative",
    "Electronic",
    "Jazz",
]
GOALS = [
    "Find collaborators",
    "Plan a release",
    "Understand royalties",
    "Grow my audience",
    "Find opportunities",
    "Build my profile",
]


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, name=""):
        email = self.normalize_email(email).strip().lower()
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email)
        user.set_password(password)
        user.save()
        CreatorProfile.objects.create(user=user, name=name.strip())
        return user

    def create_superuser(self, email, password=None, **kwargs):
        user = self.create_user(email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        return user


class User(AbstractBaseUser, PermissionsMixin):
    # Legacy scrypt encodings include a 128-character hex digest plus salt/prefix.
    password = models.CharField(max_length=256)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    onboarding_steps = models.JSONField(default=list, blank=True)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    # Incremented on every accepted workspace write; the API rejects a write
    # that carries a stale value with 409, exactly as the Node server did.
    workspace_revision = models.IntegerField(default=0)

    USERNAME_FIELD = "email"
    objects = UserManager()

    class Meta:
        db_table = "accounts_user"

    def __str__(self):
        return self.email


class CreatorProfile(models.Model):
    """PRD 8.2. Visibility flags exist per field where sensitive data is involved."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    name = models.CharField(max_length=300, blank=True)
    photo = models.CharField(max_length=300, blank=True)
    role = models.CharField(max_length=300, default="Artist")
    city = models.CharField(max_length=300, blank=True)
    bio = models.TextField(max_length=1000, blank=True)
    portfolio = models.CharField(max_length=300, blank=True)
    genres = models.JSONField(default=list, blank=True)
    goals = models.JSONField(default=list, blank=True)
    city_public = models.BooleanField(default=True)
    portfolio_public = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    username = models.SlugField(max_length=40, unique=True, null=True, blank=True)
    country = models.CharField(max_length=120, blank=True)
    skills = models.JSONField(default=list, blank=True)
    availability = models.CharField(max_length=200, blank=True)
    published = models.BooleanField(default=False, db_index=True)
    photo_public = models.BooleanField(default=False)
    availability_public = models.BooleanField(default=False)

    def __str__(self):
        return self.name or self.user.email

    @property
    def completeness(self):
        """Transparent criteria only; withholding optional sensitive data is not punished (PRD 8.2)."""
        checks = [
            bool(self.name.strip()),
            bool(self.role.strip()),
            bool(self.bio.strip()),
            bool(self.genres or self.skills),
            bool(self.username),
            bool(self.country),
        ]
        return round(100 * sum(checks) / len(checks))


class StoredImage(models.Model):
    """Private image bytes, owner-only, served at /api/images/<id>."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="images"
    )
    bytes = models.BinaryField(null=True, blank=True)
    byte_size = models.IntegerField(default=0)
    # Set once the bytes have been moved into private storage, which encrypts
    # them at rest when a key is configured. The column is emptied at that point.
    artifact = models.ForeignKey(
        "operations.PrivateArtifact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="images",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user"])]

    @property
    def url(self):
        return f"/api/images/{self.id}"

    def data(self):
        """The image bytes, wherever they are held."""
        if self.artifact_id:
            from operations import storage

            return storage.read(self.artifact)
        return bytes(self.bytes or b"")


class RequestLimit(models.Model):
    """Port of the request_limits table: short-window counters keyed by action."""

    key = models.CharField(max_length=200, primary_key=True)
    count = models.IntegerField(default=0)
    expires = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["expires"])]


class Consent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consents"
    )
    purpose = models.CharField(max_length=40)
    version = models.CharField(max_length=80)
    granted = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)


class EmailVerification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class Credit(models.Model):
    profile = models.ForeignKey(
        CreatorProfile, on_delete=models.CASCADE, related_name="credits"
    )
    work = models.CharField(max_length=300)
    role = models.CharField(max_length=120)
    source = models.URLField(max_length=500)
    date = models.DateField(null=True, blank=True)
    verification_state = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Self-reported"),
            ("verified", "Verified"),
            ("rejected", "Rejected"),
            ("disputed", "Disputed"),
        ],
    )


class ProfileLink(models.Model):
    profile = models.ForeignKey(
        CreatorProfile, on_delete=models.CASCADE, related_name="links"
    )
    title = models.CharField(max_length=120)
    url = models.URLField(max_length=500)
    public = models.BooleanField(default=False)
