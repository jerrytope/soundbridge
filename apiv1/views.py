"""The /api/* contract, reproduced from server/backend.js.

Status codes, error strings and payload shapes match the Node implementation so
existing clients, including the React app in src/, work unchanged against this
server.
"""

import json

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from accounts.images import ImageError, store
from accounts.models import StoredImage, User
from aiteam.gateway import AiError, configured, get_reply
from aiteam.views import _consume_allowance
from apiv1.limits import RateLimited, limit_request
from apiv1.serializers import WorkspaceError, workspace_for
from integrations.spotify import SpotifyError, search


def _json(payload, status=200):
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _error(message, status=400):
    return _json({"error": message}, status)


def _body(request, limit=2 * 1024 * 1024):
    if len(request.body) > limit:
        raise WorkspaceError("The request is too large.")
    try:
        body = json.loads(request.body or b"{}")
        if not isinstance(body, dict):
            raise WorkspaceError("Send a JSON object.")
        return body
    except ValueError:
        raise WorkspaceError("Send a JSON request.")


def _public_user(user):
    return {"id": str(user.id), "email": user.email}


def _session_payload(user):
    return {
        "user": _public_user(user),
        "workspace": workspace_for(user),
        "revision": user.workspace_revision,
    }


def _account_header_ok(request):
    """Writes must name the account they belong to, as the Node server required."""
    if request.method in ("GET", "HEAD"):
        return True
    return request.headers.get("X-Soundbridge-Account") == str(request.user.id)


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return _json({"ok": True, "storage": connection.vendor})


def signup(request):
    if request.method != "POST":
        return _error("API route not found.", 404)
    if not settings.ALLOW_SIGNUP:
        return _error("Registration is currently closed.", 403)
    try:
        from accounts.security import throttle

        throttle(request)
        body = _body(request, 8000)
    except RateLimited as limited:
        return _error(limited.message, 429)
    except WorkspaceError as problem:
        return _error(str(problem))
    email = str(body.get("email", "")).strip().lower()
    password = body.get("password")
    name = body.get("name")
    if not _valid_credentials(email, password):
        return _error("Enter a valid email and a password of 12–128 characters.")
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        return _error("Enter your name (up to 100 characters).")
    if User.objects.filter(email=email).exists():
        return _error("Unable to create this account. Try signing in.", 409)
    from accounts.security import register, verification_email
    from django.core.exceptions import ValidationError

    try:
        user = register(email, password, name.strip(), body.get("consent") is True)
    except ValidationError as problem:
        return _error(" ".join(problem.messages))
    verification_email(request, user)
    login(request, user)
    return _json(_session_payload(user))


def signin(request):
    if request.method != "POST":
        return _error("API route not found.", 404)
    try:
        from accounts.security import throttle

        throttle(request)
        body = _body(request, 8000)
    except RateLimited as limited:
        return _error(limited.message, 429)
    except WorkspaceError as problem:
        return _error(str(problem))
    email = str(body.get("email", "")).strip().lower()
    password = body.get("password")
    if not _valid_credentials(email, password):
        return _error("Enter a valid email and a password of 12–128 characters.")
    user = authenticate(request, email=email, password=password)
    if user is None:
        return _error("Email or password is incorrect.", 401)
    login(request, user)
    return _json(_session_payload(user))


def _valid_credentials(email, password):
    return (
        "@" in email
        and " " not in email
        and len(email) <= 254
        and isinstance(password, str)
        and settings.PASSWORD_MIN_LENGTH
        <= len(password)
        <= settings.PASSWORD_MAX_LENGTH
    )


@ensure_csrf_cookie
def session(request):
    if not request.user.is_authenticated:
        return _json({"user": None})
    return _json(_session_payload(request.user))


def sign_out(request):
    if request.method != "POST":
        return _error("Use POST to sign out.", 405)
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    if not _account_header_ok(request):
        return _error(
            "Your account changed in another tab. Reload before continuing.", 409
        )
    logout(request)
    return _json({"ok": True})


def workspace(request):
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    if not _account_header_ok(request):
        return _error(
            "Your account changed in another tab. Reload before continuing.", 409
        )
    user = request.user
    if request.method == "GET":
        return _json(
            {"workspace": workspace_for(user), "revision": user.workspace_revision}
        )
    if request.method != "PUT":
        return _error("API route not found.", 404)
    return _error(
        "Workspace replacement has been retired. Use the SoundBridge workspace screens or versioned resource APIs.",
        410,
    )


def images(request):
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    if request.method != "POST":
        return _error("API route not found.", 404)
    if not _account_header_ok(request):
        return _error(
            "Your account changed in another tab. Reload before continuing.", 409
        )
    try:
        body = _body(request, 8 * 1024 * 1024)
        image = store(request.user, body.get("image"))
    except WorkspaceError as problem:
        return _error(str(problem))
    except ImageError as problem:
        message = str(problem)
        status = (
            413
            if "smaller than 5 MB" in message or "storage is full" in message
            else 400
        )
        return _error(message, status)
    return _json({"url": image.url}, 201)


def image_detail(request, image_id):
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    image = StoredImage.objects.filter(pk=image_id, user=request.user).first()
    if request.method == "GET":
        if not image:
            return _error("Image not found.", 404)
        response = HttpResponse(image.data(), content_type="image/jpeg")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    if request.method != "DELETE":
        return _error("API route not found.", 404)
    if not _account_header_ok(request):
        return _error(
            "Your account changed in another tab. Reload before continuing.", 409
        )
    if not image:
        return _json({"ok": True})
    if _image_in_use(request.user, image.url):
        return _error("This image is still in use.", 409)
    image.delete()
    return _json({"ok": True})


def _image_in_use(user, url):
    if user.profile.photo == url:
        return True
    return user.releases.filter(artwork=url).exists()


def integrations_status(request):
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    return _json(
        {
            "openai": bool(settings.OPENAI_API_KEY and settings.OPENAI_MODEL),
            "spotify": bool(
                settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET
            ),
        }
    )


def music_search(request):
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    try:
        limit_request(f"music:{request.user.id}", 20)
        result = search(
            request.GET.get("q", ""),
            request.GET.get("type", "artist"),
            request.GET.get("market", "NG"),
        )
    except RateLimited as limited:
        return _error(limited.message, 429)
    except SpotifyError as problem:
        return _error(problem.message, problem.status)
    return _json(result)


def ai_status(request):
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    return _json({"configured": configured()})


def ai_chat(request):
    if not request.user.is_authenticated:
        return _error("Sign in to continue.", 401)
    if request.method != "POST":
        return _error("Method not allowed.", 405)
    if not _account_header_ok(request):
        return _error(
            "Your account changed in another tab. Reload before continuing.", 409
        )
    if not request.content_type or not request.content_type.startswith(
        "application/json"
    ):
        return _error("Send a JSON request.", 415)
    if not configured():
        return _error(
            "AI is not configured. Add OPENAI_API_KEY and OPENAI_MODEL on the server.",
            503,
        )
    limit_message = _consume_allowance(request.user)
    if limit_message:
        return _error(limit_message, 429)
    try:
        body = _body(request, 120000)
        from aiteam.agents import artist_context

        if not isinstance(body, dict):
            return _error("Send a JSON object.")
        body["context"] = artist_context(request.user)
        body["handoff"] = None
        return _json(get_reply(body, user=request.user))
    except WorkspaceError as problem:
        return _error(str(problem))
    except AiError as problem:
        return _error(problem.message, problem.status)
