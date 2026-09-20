"""Short-window request counters, ported from limitRequest() in server/backend.js."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import RequestLimit


class RateLimited(Exception):
    message = 'Too many requests. Try again in a minute.'


def limit_request(key, limit, window=60):
    """Count one request against `key`; raise RateLimited past `limit` per window."""
    now = timezone.now()
    RequestLimit.objects.filter(expires__lte=now).delete()
    with transaction.atomic():
        row, created = RequestLimit.objects.select_for_update().get_or_create(
            key=key, defaults={'count': 1, 'expires': now + timedelta(seconds=window)}
        )
        if created:
            return
        if row.count >= limit:
            raise RateLimited()
        row.count += 1
        row.save(update_fields=['count'])
