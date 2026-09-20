from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from network.models import Opportunity, SavedOpportunity, OpportunityApplication, Report
from operations.services import audit


@login_required
@require_http_methods(["GET", "POST"])
def directory(request):
    listings = Opportunity.objects.filter(
        is_sample=False, verification_state="verified"
    ).filter(Q(deadline__isnull=True) | Q(deadline__gte=timezone.localdate()))
    if request.method == "POST":
        item = get_object_or_404(listings, slug=request.POST.get("slug"))
        action = request.POST.get("action", "draft")
        if action == "save":
            SavedOpportunity.objects.get_or_create(user=request.user, opportunity=item)
        elif action == "unsave":
            SavedOpportunity.objects.filter(
                user=request.user, opportunity=item
            ).delete()
        elif action == "report":
            reason = request.POST.get("reason", "").strip()
            if reason:
                report = Report.objects.create(
                    reporter=request.user, opportunity=item, reason=reason[:4000]
                )
                audit(request.user, "opportunity.reported", report)
        elif action in ("draft", "applied", "withdrawn"):
            if action == "draft" and len(request.POST.get("pitch", "").strip()) < 20:
                messages.error(
                    request, "Enter at least 20 characters for an application draft."
                )
                return redirect("/opportunities")
            row, _ = OpportunityApplication.objects.get_or_create(
                user=request.user, opportunity=item, defaults={"pitch": ""}
            )
            row.pitch = request.POST.get("pitch", row.pitch)[:8000]
            row.status = action
            row.save()
            audit(request.user, "opportunity.application.updated", row)
        return redirect("/opportunities")
    if request.GET.get("type"):
        listings = listings.filter(type__iexact=request.GET["type"][:60])
    if request.GET.get("region"):
        listings = listings.filter(city__icontains=request.GET["region"][:120])
    saved = set(
        SavedOpportunity.objects.filter(user=request.user).values_list(
            "opportunity_id", flat=True
        )
    )
    if request.GET.get("saved") == "1":
        listings = listings.filter(pk__in=saved)
    page = Paginator(listings.order_by("deadline", "pk"), 20).get_page(
        request.GET.get("page")
    )
    apps = {row.opportunity_id: row for row in request.user.applications.all()}
    for item in page:
        item.saved = item.pk in saved
        item.application = apps.get(item.pk)
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "network/opportunities.html",
        {"page_obj": page, "query": params.urlencode()},
    )
