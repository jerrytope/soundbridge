"""Payment provider adapters.

Which provider SoundBridge uses is a commercial decision that has not been
made, so no provider is implemented here. What is implemented is everything
around one: a registry, the contract an adapter must satisfy, signature
verification as a required step, and normalised events the rest of the billing
code understands. Selecting a provider means writing one subclass and setting
`SOUNDBRIDGE_BILLING_PROVIDER`; nothing else in the application changes.

An adapter returns normalised events shaped like:

    {
        "event_id": "evt_123",              # provider's own id, used for idempotency
        "type": "subscription.updated",     # or subscription.cancelled
        "reference": "sub_123",             # provider's subscription id
        "email": "creator@example.com",     # account the subscription belongs to
        "plan_code": "pro",                 # must match an approved Plan
        "state": "active",                  # active | past_due | cancelled | expired
        "access_until": datetime,           # entitlement end, from the provider
        "cancel_at_period_end": False,
    }
"""

from django.conf import settings

REGISTRY = {}


class ProviderNotConfigured(Exception):
    """Raised when billing is used before a provider has been selected."""


class ProviderError(Exception):
    """Raised when a provider call or a webhook cannot be trusted."""


def register(provider_class):
    """Register an adapter. Use as a decorator on the class."""
    REGISTRY[provider_class.name] = provider_class
    return provider_class


def get_provider():
    name = settings.BILLING_PROVIDER
    if not name:
        raise ProviderNotConfigured(
            "No payment provider is configured. Set SOUNDBRIDGE_BILLING_PROVIDER "
            "once a provider and its commercial terms have been approved."
        )
    if name not in REGISTRY:
        raise ProviderNotConfigured(
            f"Billing provider '{name}' has no adapter. Implement billing.providers.Provider "
            "for it and register the subclass."
        )
    return REGISTRY[name]()


def configured():
    try:
        get_provider()
    except ProviderNotConfigured:
        return False
    return True


class Provider:
    """The contract an adapter satisfies.

    Every method raises by default: an unfinished adapter must fail loudly
    rather than quietly grant access to a paid plan.
    """

    name = ""

    def start_checkout(self, user, plan, return_url):
        """Return a URL to send the creator to, having created a provider session.

        The redirect must never grant the plan by itself; entitlement follows
        the verified webhook or a reconciliation read.
        """
        raise NotImplementedError

    def verify_event(self, request):
        """Verify the webhook signature and return one normalised event.

        Raise ProviderError when the signature, timestamp or payload cannot be
        trusted. Returning an unverified event is a security defect.
        """
        raise NotImplementedError

    def fetch_subscription(self, reference):
        """Read a subscription from the provider for reconciliation.

        Return a normalised event dict, or None when the provider has no such
        subscription.
        """
        raise NotImplementedError

    def cancel(self, reference, at_period_end=True):
        """Ask the provider to cancel. Return the normalised event that follows."""
        raise NotImplementedError
