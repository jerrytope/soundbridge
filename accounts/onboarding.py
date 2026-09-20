from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from accounts.models import User

PATHS = {
    "role": "/onboarding",
    "goals": "/goals",
    "profile": "/profile-setup",
    "genres": "/genres",
    "royalties": "/royalty-setup",
    "release": "/release-setup",
}


def required_steps(user):
    steps = ["role", "goals", "profile", "genres"]
    goals = user.profile.goals
    if "Understand royalties" in goals:
        steps.append("royalties")
    if "Plan a release" in goals:
        steps.append("release")
    return steps


def next_path(user):
    return next(
        (
            PATHS[key]
            for key in required_steps(user)
            if key not in user.onboarding_steps
        ),
        "/portal",
    )


@login_required
@require_POST
def complete_step(request, step):
    if step not in PATHS:
        return redirect("/onboarding")
    user = request.user
    profile = user.profile
    error = ""
    if step == "goals" and not profile.goals:
        error = "Choose at least one goal."
    if step == "profile" and not all(
        [
            profile.name.strip(),
            profile.username,
            profile.country.strip(),
            profile.bio.strip(),
        ]
    ):
        error = "Complete your name, username, country or region, and biography."
    if step == "genres" and not profile.genres and not profile.skills:
        error = "Choose a genre or add a skill to your profile."
    if error:
        messages.error(request, error)
        return redirect(PATHS[step])
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        user.onboarding_steps = list(dict.fromkeys(user.onboarding_steps + [step]))
        target = next_path(user)
        user.onboarding_completed_at = timezone.now() if target == "/portal" else None
        user.save(update_fields=["onboarding_steps", "onboarding_completed_at"])
    return redirect(target)
