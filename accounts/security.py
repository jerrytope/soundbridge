import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from accounts.models import Consent, EmailVerification, User
from apiv1.limits import limit_request
from operations.services import audit, queue_email


def verified(user):
    """Whether `user` clears the email-verification gate.

    With SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION off every account clears it,
    including ones registered before it was switched off, which would otherwise
    stay locked out of the workspace with no way to confirm an address.
    """
    if not settings.REQUIRE_EMAIL_VERIFICATION:
        return True
    return bool(user.email_verified_at)


def verified_filter(prefix=""):
    """`verified()` as a queryset constraint, for listing other people's rows.

    Returns an empty Q while the gate is off, which matches everyone rather than
    hiding every account registered before it was switched off.
    """
    if not settings.REQUIRE_EMAIL_VERIFICATION:
        return Q()
    return Q(**{f"{prefix}email_verified_at__isnull": False})


def throttle(request, email="", action="auth"):
    # Do not trust client-supplied forwarding headers.
    address = request.META.get("REMOTE_ADDR", "unknown")
    digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    limit_request(f"{action}:ip:{address}", 10)
    if email:
        limit_request(f"{action}:email:{digest}", 10)


def register(email, password, name, accepted):
    from accounts.views import _signup_error

    error = _signup_error(email, password, name)
    if error:
        raise ValidationError(error)
    if not accepted or not settings.TERMS_VERSION or not settings.PRIVACY_VERSION:
        raise ValidationError(
            "Accept the current terms and privacy notice to create an account."
        )
    if settings.PUBLIC_ORIGIN:
        from operations.models import LaunchDecision

        approved = LaunchDecision.objects.filter(
            key__in=["terms-copy", "privacy-copy"], approved_at__isnull=False
        ).count()
        if approved != 2:
            raise ValidationError(
                "Public registration is unavailable until approved terms and privacy notices are published."
            )
    try:
        with transaction.atomic():
            user = User.objects.create_user(email=email, password=password, name=name)
            for purpose, version in [
                ("terms", settings.TERMS_VERSION),
                ("privacy", settings.PRIVACY_VERSION),
            ]:
                Consent.objects.create(
                    user=user, purpose=purpose, version=version, granted=True
                )
            if not settings.REQUIRE_EMAIL_VERIFICATION:
                # Nothing will ever confirm this address, so record it as
                # verified now rather than leaving every account in a pending
                # state that the rest of the product reads as "not ready".
                user.email_verified_at = timezone.now()
                user.save(update_fields=["email_verified_at"])
            audit(user, "account.registered", user)
            return user
    except IntegrityError:
        raise ValidationError("Unable to create this account. Try signing in.")


def verification_email(request, user):
    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        EmailVerification.objects.filter(user=user, used_at=None).update(
            used_at=timezone.now()
        )
        row = EmailVerification.objects.create(
            user=user,
            token_digest=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=24),
        )
        link = request.build_absolute_uri(f"/verify-email/{token}")
        queue_email(
            user,
            "Verify your SoundBridge email",
            f"Confirm your email address within 24 hours:\n{link}",
            f"verify:{row.pk}",
        )


def verify_token(token):
    with transaction.atomic():
        row = (
            EmailVerification.objects.select_for_update()
            .select_related("user")
            .filter(
                token_digest=hashlib.sha256(token.encode()).hexdigest(),
                used_at=None,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if not row:
            return False
        row.used_at = timezone.now()
        row.save(update_fields=["used_at"])
        row.user.email_verified_at = row.used_at
        row.user.save(update_fields=["email_verified_at"])
        audit(row.user, "email.verified", row.user)
        return True
