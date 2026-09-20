import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods
from accounts.models import CreatorProfile, User
from apiv1.limits import limit_request, RateLimited
from network.models import CreatorConnection, UserBlock, Report, ThreadPreference
from network import services
from accounts.security import verified_filter
from operations.services import audit


@login_required
def discover(request):
    profiles = CreatorProfile.objects.filter(
        verified_filter("user__"), published=True, user__is_active=True
    ).exclude(user=request.user)
    hidden = list(
        UserBlock.objects.filter(owner=request.user).values_list("target_id", flat=True)
    ) + list(
        UserBlock.objects.filter(target=request.user).values_list("owner_id", flat=True)
    )
    profiles = profiles.exclude(user_id__in=hidden)
    search = request.GET.get("search", "").strip()[:200]
    if search:
        profiles = profiles.filter(
            Q(name__icontains=search)
            | Q(username__icontains=search)
            | Q(bio__icontains=search)
        )
    for field in ("role", "country"):
        if request.GET.get(field):
            profiles = profiles.filter(**{field + "__iexact": request.GET[field][:120]})
    if request.GET.get("city"):
        profiles = profiles.filter(
            city_public=True, city__icontains=request.GET["city"][:120]
        )
    # JSON text matching is a portable pre-filter; normalized skill indexing is a later optimization.
    for field, param in [("genres", "genre"), ("skills", "skill")]:
        if request.GET.get(param):
            profiles = profiles.filter(
                **{field + "__icontains": request.GET[param][:100]}
            )
    page = Paginator(profiles.order_by("name", "pk"), 20).get_page(
        request.GET.get("page")
    )
    for profile in page:
        matches = sorted(set(profile.genres) & set(request.user.profile.genres))
        profile.match_reason = (
            "Shared genres: " + ", ".join(matches)
            if matches
            else "Matches your selected search filters."
        )
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request, "network/people.html", {"page_obj": page, "query": params.urlencode()}
    )


@login_required
@require_POST
def connect(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    try:
        limit_request(f"connect:{request.user.pk}", 10)
        services.request_connection(request.user, target)
        messages.success(request, "Connection request saved.")
    except (ValidationError, RateLimited) as error:
        messages.error(request, getattr(error, "message", str(error)))
    return redirect("/connections")


@login_required
def connections(request):
    rows = (
        CreatorConnection.objects.filter(
            Q(requester=request.user) | Q(recipient=request.user)
        )
        .select_related("requester__profile", "recipient__profile")
        .order_by("-updated_at")
    )
    return render(
        request,
        "network/connections.html",
        {
            "page_obj": Paginator(rows, 20).get_page(request.GET.get("page")),
            "blocks": request.user.blocks.select_related("target__profile"),
        },
    )


@login_required
@require_POST
def connection_action(request, connection_id):
    connection = get_object_or_404(
        CreatorConnection.objects.select_related("requester", "recipient"),
        pk=connection_id,
    )
    try:
        services.transition_connection(
            request.user, connection, request.POST.get("action")
        )
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect("/connections")


@login_required
@require_POST
def block(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if request.POST.get("action") == "unblock":
        row = UserBlock.objects.filter(owner=request.user, target=target).first()
        if row:
            audit(request.user, "user.unblocked", row)
            row.delete()
    else:
        services.block_user(request.user, target)
    return redirect("/connections")


@login_required
@require_http_methods(["GET", "POST"])
def thread(request, connection_id):
    connection = get_object_or_404(
        CreatorConnection.objects.select_related("requester", "recipient"),
        pk=connection_id,
    )
    services.require_thread(request.user, connection, reading=request.method == "GET")
    if request.method == "POST":
        if request.POST.get("action") == "mute":
            ThreadPreference.objects.update_or_create(
                user=request.user,
                connection=connection,
                defaults={"muted": request.POST.get("muted") == "on"},
            )
        else:
            try:
                limit_request(f"message:{request.user.pk}", 30)
                services.send_message(
                    request.user,
                    connection,
                    request.POST.get("body", ""),
                    uuid.UUID(request.POST.get("client_id", "")),
                )
            except (ValidationError, ValueError, RateLimited) as error:
                messages.error(request, str(error))
        return redirect(f"/messages/{connection.pk}")
    rows = connection.messages.select_related("sender__profile").order_by(
        "-created_at", "-id"
    )
    page = Paginator(rows, 30).get_page(request.GET.get("page"))
    if request.GET.get("format") == "json":
        return JsonResponse(
            {
                "messages": [
                    {
                        "id": str(row.pk),
                        "sender": row.sender.profile.name,
                        "body": row.body,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in reversed(page.object_list)
                ]
            }
        )
    return render(
        request,
        "network/thread.html",
        {
            "connection": connection,
            "page_obj": page,
            "thread_messages": reversed(page.object_list),
            "client_id": uuid.uuid4(),
            "muted": ThreadPreference.objects.filter(
                user=request.user, connection=connection, muted=True
            ).exists(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def report(request):
    from django import forms

    class ReportForm(forms.Form):
        reason = forms.CharField(max_length=4000, widget=forms.Textarea)

    form = ReportForm(request.POST or None)
    target = get_object_or_404(User, pk=request.GET.get("user"))
    if request.method == "POST" and form.is_valid():
        try:
            limit_request(f"report:{request.user.pk}", 5, 3600)
        except RateLimited:
            form.add_error(None, "Too many reports. Please try again later.")
        else:
            row = Report.objects.create(
                reporter=request.user,
                target_user=target,
                reason=form.cleaned_data["reason"],
            )
            audit(request.user, "report.created", row)
            messages.success(request, "Report received for review.")
            return redirect("/connections")
    return render(
        request, "form.html", {"title": "Report profile or messages", "form": form}
    )
