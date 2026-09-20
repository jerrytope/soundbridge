"""Dashboard, discovery, collaborations, opportunities and analytics screens."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.models import GENRES
from accounts.views import _bump
from network.models import (
    Collaboration,
    Connection,
    Creator,
    Opportunity,
    OpportunityApplication,
)
from releases.models import ReleaseProject
from royalties.services import totals

# The three avatar colours cycled through in CreatorCard (src/main.jsx).
AVATAR_COLOURS = ["#c8f36c", "#b6a1ed", "#e9a7c8"]


def _decorate(creators, saved_ids):
    for creator in creators:
        creator.avatar_colour = AVATAR_COLOURS[creator.external_id % 3]
        creator.saved = creator.id in saved_ids
    return creators


def _saved_ids(user):
    return set(
        Connection.objects.filter(user=user).values_list("creator_id", flat=True)
    )


@login_required
def dashboard(request):
    """Port of src/components/Dashboard.jsx."""
    if not request.user.onboarding_completed_at:
        from accounts.onboarding import next_path

        return redirect(next_path(request.user))
    profile = request.user.profile
    completion = profile.completeness
    release = (
        ReleaseProject.objects.filter(owner=request.user).order_by("created_at").last()
    )
    tasks = list(release.tasks.all()) if release else []
    done = sum(1 for task in tasks if task.done)
    stats = [
        {
            "value": f"{completion}%",
            "label": "Profile complete",
            "detail": "Ready to make connections"
            if completion == 100
            else "Let people get to know you",
            "icon": "people",
            "to": "/settings",
            "progress": completion,
        },
        {
            "value": Connection.objects.filter(user=request.user).count(),
            "label": "Saved creators",
            "detail": "Your future creative circle",
            "icon": "people",
            "to": "/collaborations",
        },
        {
            "value": ReleaseProject.objects.filter(owner=request.user).count(),
            "label": "Release plans",
            "detail": "Ideas on their way to the world",
            "icon": "music",
            "to": "/release-planner",
        },
        {
            "value": request.user.ai_conversations.count(),
            "label": "AI conversations",
            "detail": "Your team is one question away",
            "icon": "spark",
            "to": "/assistants",
        },
    ]
    next_moves = [
        {
            "title": "Keep your profile fresh"
            if completion == 100
            else "Introduce yourself to the network",
            "copy": "Your story, your sound, your professional identity.",
            "icon": "people",
            "to": "/settings",
        },
        {
            "title": "Find someone on your wavelength",
            "copy": "Explore artists, producers and creative collaborators.",
            "icon": "search",
            "to": "/discover",
        },
        {
            "title": "Give your next release a direction",
            "copy": "Talk through the big picture with your A&R advisor.",
            "icon": "spark",
            "to": "/assistants?agent=ar",
        },
    ]
    return render(
        request,
        "dashboard.html",
        {
            "profile": profile,
            "first_name": profile.name.split(" ")[0] if profile.name else "",
            "completion": completion,
            "stats": stats,
            "next_moves": next_moves,
            "release": release,
            "release_tasks_total": len(tasks),
            "release_done": done,
            "release_readiness": round(100 * done / len(tasks)) if tasks else 0,
            "next_tasks": [task for task in tasks if not task.done][:3],
            "current_page": "Overview",
        },
    )


@login_required
def discover(request):
    """Port of the Discover component; the filters are GET parameters now."""
    search = request.GET.get("search", "").strip()
    role = request.GET.get("role", "")
    genre = request.GET.get("genre", "")
    country = request.GET.get("country", "")
    results = Creator.objects.all()
    if role:
        results = results.filter(role=role)
    if country:
        results = results.filter(country=country)
    results = list(results)
    if search:
        needle = search.lower()
        results = [
            creator
            for creator in results
            if needle in f"{creator.name} {creator.city} {creator.bio}".lower()
        ]
    if genre:
        results = [creator for creator in results if genre in creator.genres]
    everyone = Creator.objects.all()
    return render(
        request,
        "discover.html",
        {
            "results": _decorate(results, _saved_ids(request.user)),
            "search": search,
            "role": role,
            "genre": genre,
            "country": country,
            "roles": sorted({creator.role for creator in everyone}),
            "genres": GENRES,
            "countries": sorted({creator.country for creator in everyone}),
            "current_page": "Discover",
        },
    )


@login_required
def save_creator(request, external_id):
    """Toggle a saved creator, as the CreatorCard button did."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    creator = get_object_or_404(Creator, external_id=external_id)
    existing = Connection.objects.filter(user=request.user, creator=creator).first()
    if existing:
        existing.delete()
    else:
        Connection.objects.create(user=request.user, creator=creator)
    _bump(request.user)
    target = request.POST.get("next") or "/discover"
    if not url_has_allowed_host_and_scheme(target, allowed_hosts=None):
        target = "/discover"
    return redirect(target)


@login_required
def creator_detail(request, external_id):
    creator = Creator.objects.filter(external_id=external_id).first()
    if creator:
        _decorate([creator], _saved_ids(request.user))
    return render(
        request,
        "creator.html",
        {"creator": creator, "current_page": creator.name if creator else "creators"},
    )


@login_required
def collaborations(request):
    """Port of the Collaborations component."""
    if request.method == "POST":
        action = request.POST.get("action", "create")
        if action == "toggle":
            project = get_object_or_404(
                Collaboration, pk=request.POST.get("id"), owner=request.user
            )
            project.done = not project.done
            project.state = (
                Collaboration.COMPLETED if project.done else Collaboration.ACTIVE
            )
            project.save(update_fields=["done", "state"])
        else:
            title = (request.POST.get("title") or "").strip()
            brief = (request.POST.get("brief") or "").strip()
            if title and brief:
                from billing.services import EntitlementRequired, check

                try:
                    check(
                        request.user,
                        "active_collaborations",
                        Collaboration.objects.filter(owner=request.user)
                        .exclude(state__in=[Collaboration.COMPLETED, Collaboration.CANCELLED])
                        .count(),
                        "Active collaborations",
                    )
                except EntitlementRequired as limited:
                    messages.info(request, limited.message)
                    return redirect("/collaborations")
                Collaboration.objects.create(
                    owner=request.user,
                    title=title[:300],
                    brief=brief[:4000],
                    collaborator=(request.POST.get("creator") or "Not assigned")[:300],
                    state=Collaboration.DRAFT,
                )
        _bump(request.user)
        return redirect("/collaborations")
    saved = Creator.objects.filter(id__in=_saved_ids(request.user))
    return render(
        request,
        "collaborations.html",
        {
            "projects": Collaboration.objects.filter(owner=request.user),
            "saved_creators": _decorate(list(saved), _saved_ids(request.user)),
            "current_page": "Collaborations",
        },
    )


@login_required
def opportunities(request):
    """Port of the Opportunities component. Applications stay workspace drafts."""
    if request.method == "POST":
        opportunity = get_object_or_404(Opportunity, slug=request.POST.get("slug"))
        pitch = (request.POST.get("pitch") or "").strip()
        if len(pitch) >= 20:
            OpportunityApplication.objects.update_or_create(
                user=request.user,
                opportunity=opportunity,
                defaults={"pitch": pitch[:8000]},
            )
            _bump(request.user)
            messages.info(request, "Application draft saved.")
        return redirect(f"/opportunities?type={request.POST.get('type', 'All')}")
    kind = request.GET.get("type", "All")
    listings = Opportunity.objects.all()
    if kind != "All":
        listings = listings.filter(type=kind)
    drafts = {
        application.opportunity_id: application.pitch
        for application in OpportunityApplication.objects.filter(user=request.user)
    }
    rows = []
    for opportunity in listings:
        opportunity.pitch = drafts.get(opportunity.id, "")
        rows.append(opportunity)
    return render(
        request,
        "opportunities.html",
        {
            "opportunities": rows,
            "types": ["All", "Sync", "Collaboration", "Live"],
            "selected_type": kind,
            "current_page": "Opportunities",
        },
    )


@login_required
def analytics(request):
    """Port of the Analytics component."""
    releases = list(
        ReleaseProject.objects.filter(owner=request.user).prefetch_related("tasks")
    )
    rows = []
    completed_tasks = 0
    for release in releases:
        tasks = list(release.tasks.all())
        done = sum(1 for task in tasks if task.done)
        completed_tasks += done
        rows.append(
            {
                "title": release.title,
                "total": len(tasks),
                "done": done,
                "percent": round(100 * done / len(tasks)) if tasks else 0,
            }
        )
    statements = list(request.user.statements.all())
    stats = [
        (Connection.objects.filter(user=request.user).count(), "Saved creators"),
        (
            Collaboration.objects.filter(owner=request.user, done=True).count(),
            "Completed collaborations",
        ),
        (completed_tasks, "Completed release tasks"),
        (len(statements), "Imported statements"),
    ]
    return render(
        request,
        "analytics.html",
        {
            "stats": stats,
            "releases": rows,
            "earnings": sorted(totals(statements).items()),
            "current_page": "Analytics",
        },
    )
