from django.utils import timezone
from .models import AuditEvent, EmailDelivery, Notification, NotificationPreference


def audit(actor, action, obj):
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        resource_type=obj._meta.label_lower,
        resource_id=str(obj.pk),
    )


def notify(user, category, title, url, key):
    preference = NotificationPreference.objects.filter(
        user=user, category=category
    ).first()
    if preference is None or preference.in_app:
        Notification.objects.get_or_create(
            dedupe_key=f"{user.pk}:{key}",
            defaults={"user": user, "category": category, "title": title, "url": url},
        )
    if preference and preference.email:
        from django.conf import settings

        if settings.PUBLIC_ORIGIN:
            queue_email(
                user,
                title,
                f"{title}\n\n{settings.PUBLIC_ORIGIN}{url}",
                f"notice:{user.pk}:{key}",
            )


def queue_email(user, subject, body, key):
    return EmailDelivery.objects.get_or_create(
        dedupe_key=key,
        defaults={
            "user": user,
            "subject": subject,
            "body": body,
            "available_at": timezone.now(),
        },
    )[0]
