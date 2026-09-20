"""Membership screen, checkout start, provider webhook and cancellation.

The redirect a creator follows never grants a plan. Entitlement changes only
when a verified provider event arrives here, or when reconciliation reads the
provider directly.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from billing.models import Plan, Subscription
from billing.providers import ProviderError, ProviderNotConfigured, configured, get_provider
from billing.services import (
    BillingError,
    CAPABILITIES,
    apply_event,
    cancel_subscription,
    current_plan,
    unlimited,
)
from operations.services import audit


@login_required
def membership(request):
    plan = current_plan(request.user)
    return render(
        request,
        "billing/membership.html",
        {
            "plan": plan,
            "plans": Plan.objects.filter(approved_at__isnull=False),
            "subscription": Subscription.objects.filter(user=request.user).first(),
            "provider_ready": configured(),
            "unlimited": unlimited(),
            "capabilities": CAPABILITIES,
        },
    )


@login_required
@require_POST
def checkout(request):
    """Start a provider checkout for an approved plan."""
    plan = get_object_or_404(
        Plan, code=request.POST.get("plan"), approved_at__isnull=False
    )
    try:
        provider = get_provider()
    except ProviderNotConfigured as problem:
        messages.info(request, str(problem))
        return redirect("/membership")
    try:
        url = provider.start_checkout(request.user, plan, request.build_absolute_uri("/membership"))
    except (NotImplementedError, ProviderError) as problem:
        messages.error(
            request,
            "Checkout is unavailable. No charge was made. " + str(problem),
        )
        return redirect("/membership")
    audit(request.user, "billing.checkout.started", plan)
    return redirect(url)


@login_required
@require_POST
def cancel(request):
    try:
        cancel_subscription(request.user, at_period_end=True)
    except (ProviderNotConfigured, NotImplementedError, ProviderError, BillingError) as problem:
        messages.error(request, str(problem))
        return redirect("/membership")
    messages.success(
        request,
        "Cancellation requested. Your plan stays active until the end of the paid period, "
        "and your data is kept.",
    )
    return redirect("/membership")


@csrf_exempt
def webhook(request):
    """Receive provider events. The adapter verifies the signature."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        provider = get_provider()
    except ProviderNotConfigured:
        # Nothing may be trusted before a provider is selected.
        return JsonResponse({"error": "billing_not_configured"}, status=503)
    try:
        event = provider.verify_event(request)
    except ProviderError:
        return JsonResponse({"error": "signature_rejected"}, status=400)
    except (NotImplementedError, json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "unreadable_event"}, status=400)
    try:
        apply_event(provider.name, event)
    except BillingError as problem:
        # Acknowledge with a client error so the provider stops retrying an
        # event this workspace can never apply, and leave a trace to follow up.
        return JsonResponse({"error": "not_applicable", "detail": str(problem)}, status=422)
    return HttpResponse(status=204)
