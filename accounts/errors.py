from django.http import JsonResponse
from django.shortcuts import render


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/v1/"):
        return JsonResponse(
            {
                "error": {
                    "code": "csrf_failed",
                    "message": "Refresh your session and send a valid CSRF token.",
                }
            },
            status=403,
        )
    if request.path.startswith("/api/"):
        return JsonResponse(
            {"error": "Refresh your session and send a valid CSRF token."}, status=403
        )
    return render(
        request,
        "accounts/recovery.html",
        {
            "title": "Please refresh this page",
            "recovery_message": "Your form security token is missing or expired. Return to the form, refresh it, and try again.",
        },
        status=403,
    )
