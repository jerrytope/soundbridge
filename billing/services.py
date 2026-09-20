"""Server-owned entitlements.

A plan's limits are commercial decisions, so they live in approved `Plan`
records rather than in code. This module only answers two questions: what is
this account allowed to do, and has it reached the limit.

Capability keys are listed here so an operator filling in a plan knows exactly
which ones the application reads. A capability missing from an approved plan is
disabled, which is the fail-closed reading of PRD section 11.

Development without any approved plan stays unlimited, because an unapproved
environment has no commercial terms to enforce. Once a public origin is
configured the limits are whatever the approved plans say, and nothing else.
"""

from django.conf import settings
from django.utils import timezone

from billing.models import Plan, Subscription

CAPABILITIES = {
    "ai_daily": "AI specialist requests per UTC day",
    "release_plans": "Release plans an account may keep",
    "active_collaborations": "Collaboration briefs that are not completed or cancelled",
    "saved_calculations": "Saved royalty scenarios",
    "statements": "Imported royalty statements",
    "connection_requests_daily": "Connection requests sent per UTC day",
}


class EntitlementRequired(Exception):
    """Raised when an action would exceed the account's approved plan."""

    def __init__(self, message, capability):
        super().__init__(message)
        self.message = message
        self.capability = capability


def current_plan(user):
    subscription = (
        Subscription.objects.select_related("plan")
        .filter(
            user=user,
            state__in=["active", "cancelled"],
            access_until__gt=timezone.now(),
            plan__approved_at__isnull=False,
        )
        .first()
    )
    if subscription:
        return subscription.plan
    return Plan.objects.filter(code="free", approved_at__isnull=False).first()


def unlimited():
    """True while no approved commercial plan exists outside a public deployment."""
    return not settings.PUBLIC_ORIGIN and not Plan.objects.filter(
        approved_at__isnull=False
    ).exists()


def allowance(user, capability):
    """The numeric limit, or None when nothing is being enforced yet."""
    if unlimited():
        if capability == "ai_daily":
            # The development AI allowance protects the provider bill, not revenue.
            return settings.AI_DAILY_LIMIT
        return None
    return limit(user, capability)


def limit(user, capability):
    plan = current_plan(user)
    if plan:
        value = plan.limits.get(capability, 0)
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else 0
        )
    # Existing development allowance is not an approved commercial Free plan.
    if not settings.PUBLIC_ORIGIN and capability == "ai_daily":
        return settings.AI_DAILY_LIMIT
    return 0


def remaining(user, capability, used):
    value = allowance(user, capability)
    if value is None:
        return None
    return max(0, value - used)


def check(user, capability, used, noun):
    """Raise EntitlementRequired when `used` already fills the allowance.

    `noun` names what is being added, so the message tells the creator what
    happened without inventing a price or a plan name.
    """
    value = allowance(user, capability)
    if value is None:
        return
    if used >= value:
        if value == 0:
            raise EntitlementRequired(
                f"{noun} are not included in your current plan.", capability
            )
        raise EntitlementRequired(
            f"Your plan includes {value} {noun.lower()}. Remove one or change your plan to add another.",
            capability,
        )


# --- Subscription lifecycle -------------------------------------------------
#
# Entitlement comes from verified provider events and from reconciliation
# reads, never from a browser redirect. Every event is recorded once, so a
# provider that retries or reorders deliveries cannot double-apply or regress a
# subscription to an older state.


class BillingError(Exception):
    """Raised when an event cannot be applied to an account or plan."""


def _resolve(event):
    from accounts.models import User

    required = {"event_id", "type", "reference", "state", "access_until"}
    missing = required - set(event)
    if missing:
        raise BillingError(f"Provider event is missing {', '.join(sorted(missing))}.")
    user = User.objects.filter(email=str(event.get("email", "")).strip().lower()).first()
    if user is None:
        raise BillingError("Provider event names an account that does not exist here.")
    plan = Plan.objects.filter(
        code=event.get("plan_code"), approved_at__isnull=False
    ).first()
    if plan is None:
        raise BillingError(
            "Provider event names a plan that is not approved in this workspace."
        )
    return user, plan


def record_event(provider, event):
    """Store the provider event once. Returns False when it was already seen.

    The insert runs in its own savepoint so a duplicate delivery does not break
    the surrounding transaction; a provider that retries is normal, not an error.
    """
    from django.db import IntegrityError, transaction

    from billing.models import BillingEvent

    try:
        with transaction.atomic():
            BillingEvent.objects.create(
                provider=provider, provider_event_id=str(event["event_id"])
            )
    except IntegrityError:
        return False
    return True


def apply_event(provider, event):
    """Apply one verified, normalised provider event. Idempotent by event id."""
    from django.db import transaction
    from django.utils import timezone as tz

    from billing.models import BillingEvent
    from operations.services import audit

    user, plan = _resolve(event)
    with transaction.atomic():
        if not record_event(provider, event):
            return Subscription.objects.filter(user=user).first()
        subscription, _ = Subscription.objects.select_for_update().get_or_create(
            user=user,
            defaults={
                "provider": provider,
                "provider_reference": str(event["reference"]),
                "plan": plan,
                "state": event["state"],
                "access_until": event["access_until"],
                "verified_at": tz.now(),
            },
        )
        subscription.provider = provider
        subscription.provider_reference = str(event["reference"])
        subscription.plan = plan
        subscription.state = event["state"]
        subscription.access_until = event["access_until"]
        subscription.cancel_at_period_end = bool(event.get("cancel_at_period_end"))
        subscription.verified_at = tz.now()
        subscription.save()
        BillingEvent.objects.filter(
            provider=provider, provider_event_id=str(event["event_id"])
        ).update(processed_at=tz.now())
        audit(user, f"billing.{event['type']}", subscription)
    return subscription


def cancel_subscription(user, at_period_end=True):
    """Ask the provider to cancel. Access continues until the paid period ends."""
    from billing.providers import get_provider

    subscription = Subscription.objects.filter(user=user).first()
    if subscription is None:
        raise BillingError("There is no subscription to cancel.")
    provider = get_provider()
    event = provider.cancel(subscription.provider_reference, at_period_end)
    event.setdefault("email", user.email)
    event.setdefault("plan_code", subscription.plan_id)
    return apply_event(provider.name, event)


def reconcile(user=None):
    """Re-read subscriptions from the provider and correct any drift.

    Returns the number of subscriptions whose stored state changed. Run this on
    a schedule: webhooks can be missed, and entitlement must not drift from what
    the provider says was actually paid for.
    """
    from billing.providers import get_provider

    provider = get_provider()
    rows = Subscription.objects.select_related("plan", "user")
    if user is not None:
        rows = rows.filter(user=user)
    changed = 0
    for subscription in rows:
        event = provider.fetch_subscription(subscription.provider_reference)
        if event is None:
            if subscription.state != "expired":
                subscription.state = "expired"
                subscription.save(update_fields=["state"])
                changed += 1
            continue
        before = (subscription.state, subscription.access_until, subscription.plan_id)
        event.setdefault("email", subscription.user.email)
        event.setdefault("event_id", f"reconcile:{subscription.provider_reference}:{event['state']}:{event['access_until']}")
        event.setdefault("type", "subscription.reconciled")
        updated = apply_event(provider.name, event)
        if updated and (updated.state, updated.access_until, updated.plan_id) != before:
            changed += 1
    return changed
