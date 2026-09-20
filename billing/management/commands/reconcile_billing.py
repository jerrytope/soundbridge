from django.core.management.base import BaseCommand, CommandError
from billing.providers import ProviderNotConfigured
from billing.services import reconcile


class Command(BaseCommand):
    help = (
        "Re-read subscriptions from the payment provider and correct drift. "
        "Schedule hourly once a provider is configured."
    )

    def handle(self, **options):
        try:
            changed = reconcile()
        except ProviderNotConfigured as problem:
            raise CommandError(str(problem))
        except NotImplementedError:
            raise CommandError(
                "The configured billing provider adapter does not implement fetch_subscription()."
            )
        self.stdout.write(
            self.style.SUCCESS(f"Reconciled; {changed} subscription(s) changed.")
        )
