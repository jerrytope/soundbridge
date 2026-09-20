"""Serve the original HTML/CSS/JS prototype in legacy/.

The React app exposed these at /<page>.html through its Legacy route; the same
files are served here so old links keep working.
"""

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import render

PAGES = {
    "index",
    "signup",
    "portal",
    "discover",
    "onboarding",
    "goals",
    "genres",
    "profile-setup",
    "release-setup",
    "royalty-setup",
    "royalty-calculator",
    "royalty-upload",
}


def page(request, page):
    if settings.PUBLIC_ORIGIN or page not in PAGES:
        raise Http404("Page not found.")
    path = settings.LEGACY_DIR / f"{page}.html"
    if not path.exists():
        raise Http404("Page not found.")
    return FileResponse(path.open("rb"), content_type="text/html; charset=utf-8")


def asset(request, asset):
    if settings.PUBLIC_ORIGIN:
        raise Http404("Legacy assets are disabled in production.")
    path = settings.LEGACY_DIR / asset
    if not path.exists():
        raise Http404("Asset not found.")
    kind = "text/css" if asset.endswith(".css") else "text/javascript"
    return FileResponse(path.open("rb"), content_type=f"{kind}; charset=utf-8")


def not_found(request, exception=None):
    """Port of the React catch-all route."""
    return render(request, "not_found.html", status=404)
