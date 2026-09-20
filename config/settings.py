"""SoundBridge Django settings.

Behaviour mirrors the Node server in server/ so the existing front end and API
clients see no difference: same session cookie, same origin policy, same
password length rule and the same server-only environment variable names.
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

from config import env

BASE_DIR = Path(__file__).resolve().parent.parent

PUBLIC_ORIGIN = env.get(BASE_DIR, "SOUNDBRIDGE_PUBLIC_ORIGIN")
DEBUG = not PUBLIC_ORIGIN

# A deployment reached over plain HTTP - an IP address and a port, before a domain
# name and a certificate exist - must not be given the HTTPS-only settings below.
# The redirect would loop forever and Secure cookies would never be stored, so no
# one could sign in at all. The scheme in the declared origin decides, which means
# moving to https:// later turns the full set on by itself.
HTTPS_ORIGIN = PUBLIC_ORIGIN.startswith("https://")
SECRET_KEY = env.get(BASE_DIR, "SOUNDBRIDGE_SECRET_KEY") or (
    "insecure-development-key" if DEBUG else ""
)
if not SECRET_KEY:
    raise RuntimeError(
        "SOUNDBRIDGE_SECRET_KEY is required when a public origin is configured."
    )

# Registration closes automatically once a public origin is configured, as
# server/backend.js does with allowSignup = !publicOrigin.
ALLOW_SIGNUP = env.flag(BASE_DIR, "SOUNDBRIDGE_ALLOW_SIGNUP", not PUBLIC_ORIGIN)

# Email verification is switched off: a new account is usable immediately with the
# details it signed up with, and no confirmation link stands in the way. The whole
# verification machinery - the token model, /verify-email, the emailed link - is
# still here and still works; only the enforcement is off, so setting
# SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION=true puts the gate back without a code
# change. Accounts created while it is off are marked verified on registration.
REQUIRE_EMAIL_VERIFICATION = env.flag(
    BASE_DIR, "SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION", False
)

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
CSRF_TRUSTED_ORIGINS = []
if PUBLIC_ORIGIN:
    _host = urlparse(PUBLIC_ORIGIN).hostname
    if _host:
        ALLOWED_HOSTS = [_host]
    CSRF_TRUSTED_ORIGINS = [PUBLIC_ORIGIN]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "accounts",
    "network",
    "releases",
    "royalties",
    "aiteam",
    "integrations",
    "apiv1",
    "operations",
    "billing",
]

MIDDLEWARE = [
    "operations.telemetry.RequestTelemetryMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.middleware.RequestPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.VerificationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context.shell",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env.get(BASE_DIR, "SOUNDBRIDGE_DJANGO_DATABASE")
        or BASE_DIR / ".data" / "django.sqlite3",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 5,
            "init_command": "PRAGMA journal_mode=WAL;",
        },
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.auth.EmailBackend"]

# The Node server accepted 12-128 character passwords; keep that contract so
# existing accounts and the existing sign-up copy stay correct.
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": PASSWORD_MIN_LENGTH},
    },
]
# The legacy hasher lets accounts created by server/backend.js sign in unchanged.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "accounts.hashers.NodeScryptPasswordHasher",
]

LOGIN_URL = "/signup"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "soundbridge_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_SECURE = HTTPS_ORIGIN
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = HTTPS_ORIGIN
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if HTTPS_ORIGIN:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # TLS terminates at the ingress proxy, so Django only learns the original
    # scheme from a forwarded header. Without this the redirect above fires on
    # every proxied request and the site loops. The proxy must therefore set
    # X-Forwarded-Proto itself and strip any value a client sends; DEPLOYMENT.md
    # configures Nginx to do exactly that.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / ".data" / "staticfiles"

# The original static prototype stays reachable at /<page>.html, as the React
# app's Legacy route does.
LEGACY_DIR = BASE_DIR / "legacy"

DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024

# Server-only integration credentials. Never expose these to the browser.
OPENAI_API_KEY = env.get(BASE_DIR, "OPENAI_API_KEY")
OPENAI_MODEL = env.get(BASE_DIR, "OPENAI_MODEL")
SPOTIFY_CLIENT_ID = env.get(BASE_DIR, "SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = env.get(BASE_DIR, "SPOTIFY_CLIENT_SECRET")
AI_DAILY_LIMIT = int(env.get(BASE_DIR, "SOUNDBRIDGE_AI_DAILY_LIMIT", "30"))
AI_REQUEST_TIMEOUT = 60
IMAGE_MAX_BYTES = 5 * 1024 * 1024
IMAGE_STORAGE_PER_ACCOUNT = 20 * 1024 * 1024

# Approved production policy versions must be supplied before registration opens.
TERMS_VERSION = env.get(
    BASE_DIR, "SOUNDBRIDGE_TERMS_VERSION", "development" if DEBUG else ""
)
PRIVACY_VERSION = env.get(
    BASE_DIR, "SOUNDBRIDGE_PRIVACY_VERSION", "development" if DEBUG else ""
)
EMAIL_BACKEND = env.get(
    BASE_DIR,
    "SOUNDBRIDGE_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env.get(BASE_DIR, "EMAIL_HOST")
EMAIL_PORT = int(env.get(BASE_DIR, "EMAIL_PORT", "587"))
EMAIL_HOST_USER = env.get(BASE_DIR, "EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env.get(BASE_DIR, "EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env.flag(BASE_DIR, "EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env.get(
    BASE_DIR, "DEFAULT_FROM_EMAIL", "SoundBridge <noreply@localhost>"
)
PASSWORD_RESET_TIMEOUT = 3600
MEDIA_ROOT = BASE_DIR / ".data" / "private"

# Production runs on MySQL; SQLite above stays the zero-configuration default for
# local development. Naming a database is what switches the engine over.
#
# MySQL 8.0.16 or newer is required. The schema uses JSON columns and one CHECK
# constraint (network.CreatorConnection forbids a row pointing at itself), and
# older MySQL silently ignores CHECK constraints rather than enforcing them.
if env.get(BASE_DIR, "MYSQL_DATABASE"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env.get(BASE_DIR, "MYSQL_DATABASE"),
        "USER": env.get(BASE_DIR, "MYSQL_USER"),
        "PASSWORD": env.get(BASE_DIR, "MYSQL_PASSWORD"),
        "HOST": env.get(BASE_DIR, "MYSQL_HOST", "db"),
        "PORT": env.get(BASE_DIR, "MYSQL_PORT", "3306"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            # utf8mb4 is the only charset that stores the full range of
            # characters creators put in names, bios and track titles.
            "charset": "utf8mb4",
            # Without STRICT_TRANS_TABLES MySQL truncates oversized values and
            # accepts invalid dates instead of raising, which would silently
            # corrupt royalty figures. Django recommends setting it here so it
            # applies to every connection regardless of server configuration.
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_ai_ci"},
    }

# Tests use a fast hasher: password hashing cost is not what they exercise.
if "test" in sys.argv:
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher"
    ] + PASSWORD_HASHERS

MALWARE_SCANNER = env.get(BASE_DIR, "SOUNDBRIDGE_MALWARE_SCANNER")

# Moderation runs before a message reaches the model and before a reply is
# shown. A public deployment must configure it; without it the gateway refuses.
MODERATION_MODEL = env.get(BASE_DIR, "SOUNDBRIDGE_MODERATION_MODEL")

# The payment provider is a commercial decision. With none selected, checkout
# and the webhook refuse to act rather than pretending to charge anyone.
BILLING_PROVIDER = env.get(BASE_DIR, "SOUNDBRIDGE_BILLING_PROVIDER")
BILLING_WEBHOOK_SECRET = env.get(BASE_DIR, "SOUNDBRIDGE_BILLING_WEBHOOK_SECRET")

# Private files (data exports today) live outside the database and outside any
# served directory. With a Fernet key configured the bytes on disk are
# ciphertext; a public deployment must configure one before anything is stored.
PRIVATE_STORAGE_ROOT = env.get(
    BASE_DIR, "SOUNDBRIDGE_PRIVATE_STORAGE_ROOT"
) or (BASE_DIR / ".data" / "artifacts")
PRIVATE_STORAGE_KEY = env.get(BASE_DIR, "SOUNDBRIDGE_PRIVATE_STORAGE_KEY")

CELERY_BROKER_URL = env.get(BASE_DIR, "CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 1200
CELERY_BEAT_SCHEDULE = {
    "email-outbox": {"task": "operations.tasks.deliver_email", "schedule": 60.0},
    "scan-and-parse": {"task": "operations.tasks.process_uploads", "schedule": 60.0},
    "reminders": {"task": "operations.tasks.send_reminders", "schedule": 900.0},
    "privacy-requests": {
        "task": "operations.tasks.process_privacy",
        "schedule": 300.0,
    },
    "retention": {"task": "operations.tasks.apply_retention", "schedule": 3600.0},
}
EMAIL_TIMEOUT = 15
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"safe_json": {"()": "operations.telemetry.SafeJsonFormatter"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "safe_json"}
    },
    "loggers": {
        "soundbridge.requests": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        }
    },
}
if "test" in sys.argv:
    STORAGES["staticfiles"] = {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    }
    LOGGING["loggers"]["soundbridge.requests"]["level"] = "WARNING"

CSRF_FAILURE_VIEW = "accounts.errors.csrf_failure"
