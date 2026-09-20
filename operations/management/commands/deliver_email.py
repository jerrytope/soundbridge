from datetime import timedelta
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from operations.models import EmailDelivery


class Command(BaseCommand):
    help = "Deliver due outbox messages. Schedule every minute. Failures retry with bounded backoff."

    def handle(self, **options):
        ids = list(
            EmailDelivery.objects.filter(
                sent_at=None,
                failed_at=None,
                available_at__lte=timezone.now(),
                attempts__lt=EmailDelivery.MAX_ATTEMPTS,
            ).values_list("pk", flat=True)[:100]
        )
        for pk in ids:
            with transaction.atomic():
                row = EmailDelivery.objects.select_for_update().get(pk=pk)
                if row.sent_at or row.available_at > timezone.now():
                    continue
                row.attempts += 1
                try:
                    send_mail(
                        row.subject,
                        row.body,
                        None,
                        [row.user.email],
                        fail_silently=False,
                    )
                except Exception as problem:
                    row.last_error = type(problem).__name__[:200]
                    if row.attempts >= EmailDelivery.MAX_ATTEMPTS:
                        # Out of retries: keep the row visible as failed rather
                        # than letting the message disappear silently.
                        row.failed_at = timezone.now()
                        row.body = ""
                        row.save(
                            update_fields=[
                                "attempts",
                                "failed_at",
                                "last_error",
                                "body",
                            ]
                        )
                        self.stderr.write(
                            f"Delivery {row.pk} failed permanently after {row.attempts} attempts "
                            f"({row.last_error}). No message content logged."
                        )
                        continue
                    row.available_at = timezone.now() + timedelta(
                        minutes=min(2**row.attempts, 240)
                    )
                    row.save(
                        update_fields=["attempts", "available_at", "last_error"]
                    )
                    self.stderr.write(
                        f"Delivery {row.pk} failed; retry scheduled. No message content logged."
                    )
                else:
                    row.sent_at = timezone.now()
                    row.body = ""
                    row.save(update_fields=["attempts", "sent_at", "body"])
