"""Landing, authentication, onboarding, profile and membership screens.

Each view renders the same markup the matching React component rendered; the
only difference is that state changes arrive as form posts instead of
`update()` calls, and the data comes from the database instead of a workspace
blob.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import ValidationError, validate_password
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render

from accounts.images import ImageError, store_upload
from accounts.models import GENRES, GOALS, ROLES, CreatorProfile, StoredImage, User


def landing(request):
    # The React footer printed new Date().getFullYear(); keep that current.
    from django.utils import timezone

    return render(request, "landing.html", {"year": timezone.localdate().year})


def signup(request):
    """Create an account or sign in, matching the Signup component."""
    resume = request.GET.get("mode") == "signin"
    error = ""
    if request.method == "POST":
        from accounts.security import throttle, register, verification_email
        from apiv1.limits import RateLimited

        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        try:
            throttle(request, email)
        except RateLimited:
            return render(
                request,
                "signup.html",
                {"resume": resume, "error": "Too many requests. Try again later."},
                status=429,
            )
        if resume:
            user = authenticate(request, email=email, password=password)
            if user is None:
                error = "Email or password is incorrect."
            else:
                login(request, user)
                return redirect("/portal")
        else:
            name = (request.POST.get("name") or "").strip()
            try:
                user = register(
                    email, password, name, request.POST.get("consent") == "on"
                )
            except ValidationError as problem:
                error = " ".join(problem.messages)
            else:
                if settings.REQUIRE_EMAIL_VERIFICATION:
                    verification_email(request, user)
                    login(request, user)
                    return redirect("/verify-email")
                login(request, user)
                return redirect("/portal")
    return render(request, "signup.html", {"resume": resume, "error": error})


def _signup_error(email, password, name):
    if not settings.ALLOW_SIGNUP:
        return "Registration is currently closed."
    if not name or len(name) > 100:
        return "Enter your name (up to 100 characters)."
    if "@" not in email or len(email) > 254:
        return "Enter a valid email and a password of 12–128 characters."
    if (
        len(password) < settings.PASSWORD_MIN_LENGTH
        or len(password) > settings.PASSWORD_MAX_LENGTH
    ):
        return "Enter a valid email and a password of 12–128 characters."
    if User.objects.filter(email=email).exists():
        return "Unable to create this account. Try signing in."
    try:
        validate_password(password)
    except ValidationError as problem:
        return " ".join(problem.messages)
    return ""


def sign_out(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    logout(request)
    return redirect("/signup?mode=signin")


STEPS = {
    "onboarding": {
        "key": "role",
        "eyebrow": "LET’S GET TO KNOW YOU",
        "title": "What do you do in music?",
        "description": "Make this workspace your own.",
        "options": ROLES,
        "multiple": False,
        "next": "/goals",
    },
    "goals": {
        "key": "goals",
        "eyebrow": "LET’S GET TO KNOW YOU",
        "title": "What’s your next big move?",
        "description": "Choose up to three goals.",
        "options": GOALS,
        "multiple": True,
        "limit": 3,
        "next": "/profile-setup",
    },
    "genres": {
        "key": "genres",
        "eyebrow": "LET’S GET TO KNOW YOU",
        "title": "What does your world sound like?",
        "description": "Make this workspace your own.",
        "options": GENRES,
        "multiple": True,
        "next": "/royalty-setup",
    },
}


@login_required
def setup(request, step):
    """The role, goals and genres choice grids (the Setup component)."""
    config = STEPS[step]
    profile = request.user.profile
    if request.method == "POST":
        option = request.POST.get("option", "")
        if config["multiple"]:
            selected = list(getattr(profile, config["key"]))
            if option in selected:
                selected.remove(option)
            elif option in config["options"] and len(selected) < config.get(
                "limit", 20
            ):
                selected.append(option)
            setattr(profile, config["key"], selected)
        elif option in config["options"]:
            profile.role = option
        profile.save()
        _bump(request.user)
        return redirect(request.path)
    selected = getattr(profile, config["key"])
    if not config["multiple"]:
        selected = [selected]
    return render(
        request,
        "setup.html",
        {
            "config": config,
            "step": step,
            "selected": selected,
            "at_limit": config["multiple"] and len(selected) >= config.get("limit", 20),
            "profile": profile,
        },
    )


@login_required
def profile_view(request):
    """Profile editor. /profile-setup continues onboarding; /settings does not."""
    onboarding = request.path == "/profile-setup"
    profile = request.user.profile
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "photo":
            return _photo(request, profile)
        if action == "remove-photo":
            profile.photo = ""
            profile.save(update_fields=["photo", "updated_at"])
            _bump(request.user)
            messages.info(request, "Profile photo removed.")
            return redirect(request.path)
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.info(request, "Enter your name.")
            return redirect(request.path)
        profile.name = name[:300]
        profile.role = (request.POST.get("role") or profile.role)[:300]
        profile.city = (request.POST.get("city") or "")[:300]
        profile.bio = (request.POST.get("bio") or "")[:1000]
        portfolio = (request.POST.get("portfolio") or "").strip()[:300]
        if portfolio and not portfolio.lower().startswith(("http://", "https://")):
            messages.info(request, "Portfolio must be an HTTP or HTTPS URL.")
            return redirect(request.path)
        profile.portfolio = portfolio
        profile.save()
        _bump(request.user)
        messages.info(request, "Profile updated. Saving to your account…")
        return redirect(STEPS["genres"]["next"] if onboarding else request.path)
    return render(
        request,
        "profile.html",
        {
            "profile": profile,
            "onboarding": onboarding,
            "roles": ROLES,
            "next_url": "/genres" if onboarding else "",
        },
    )


def _photo(request, profile):
    upload = request.FILES.get("image")
    if not upload:
        return redirect(request.path)
    try:
        image = store_upload(request.user, upload)
    except ImageError as problem:
        messages.info(request, str(problem))
        return redirect(request.path)
    previous = profile.photo
    profile.photo = image.url
    profile.save(update_fields=["photo", "updated_at"])
    _bump(request.user)
    if previous.startswith("/api/images/"):
        StoredImage.objects.filter(
            user=request.user, id=previous.rsplit("/", 1)[-1]
        ).delete()
    messages.info(request, "Profile photo updated.")
    return redirect(request.path)


@login_required
def membership(request):
    return render(request, "membership.html")


@login_required
def export_workspace(request):
    return redirect("/settings/privacy")


def _bump(user):
    """Keep the revision counter moving so API clients see workspace changes."""
    from django.db.models import F

    User.objects.filter(pk=user.pk).update(
        workspace_revision=F("workspace_revision") + 1
    )
    user.refresh_from_db(fields=["workspace_revision"])


def profile_or_none(request):
    if request.user.is_authenticated:
        return CreatorProfile.objects.filter(user=request.user).first()
    return None


def integration_status(request):
    return JsonResponse(
        {
            "openai": bool(settings.OPENAI_API_KEY and settings.OPENAI_MODEL),
            "spotify": bool(
                settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET
            ),
        }
    )
