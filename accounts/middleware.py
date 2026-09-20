from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect


class VerificationMiddleware:
    """Unverified accounts can manage access and setup but cannot use the workspace."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.REQUIRE_EMAIL_VERIFICATION:
            return self.get_response(request)
        user = request.user
        allowed = (
            "/signup",
            "/sign-out",
            "/verify-email",
            "/password-reset",
            "/reset/",
            "/onboarding",
            "/setup/continue/",
            "/goals",
            "/genres",
            "/profile-setup",
            "/settings",
            "/api/auth/",
            "/api/images",
            "/people/",
            "/api/health",
            "/static/",
            "/legal/",
            "/admin/",
        )
        if (
            user.is_authenticated
            and not user.email_verified_at
            and request.path != "/"
            and not request.path.startswith(allowed)
        ):
            if request.path.startswith("/api/v1/"):
                return JsonResponse(
                    {
                        "error": {
                            "code": "email_unverified",
                            "message": "Verify your email to continue.",
                        }
                    },
                    status=403,
                )
            if request.path.startswith("/api/"):
                return JsonResponse(
                    {
                        "error": "Verify your email to continue.",
                        "code": "email_unverified",
                    },
                    status=403,
                )
            return redirect("/verify-email")
        return self.get_response(request)
