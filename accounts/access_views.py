from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from apiv1.limits import RateLimited
from accounts.security import throttle, verification_email, verify_token


@login_required
@require_http_methods(["GET", "POST"])
def verification(request):
    if request.user.email_verified_at:
        return redirect("/portal")
    if request.method == "POST":
        try:
            throttle(request, request.user.email, "verify")
            verification_email(request, request.user)
            messages.info(
                request, "Verification email queued. Check your inbox shortly."
            )
        except RateLimited:
            messages.error(request, "Too many requests. Try again later.")
    return render(request, "accounts/verify.html")


@require_http_methods(["GET", "POST"])
def confirm_email(request, token):
    # Email link scanners must not consume a token merely by opening the URL.
    if request.method == "POST":
        if verify_token(token):
            messages.success(request, "Email verified. You can sign in and continue.")
            return redirect(
                "/onboarding"
                if request.user.is_authenticated
                else "/signup?mode=signin"
            )
        messages.error(
            request,
            "This link is invalid, expired, or already used. Request a new email.",
        )
    return render(request, "accounts/verify.html", {"confirm": True})


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/recovery.html"
    email_template_name = "accounts/reset_email.txt"
    subject_template_name = "accounts/reset_subject.txt"
    success_url = "/password-reset/sent"

    def post(self, request, *args, **kwargs):
        try:
            throttle(request, request.POST.get("email", ""), "recovery")
        except RateLimited:
            return render(
                request,
                self.template_name,
                {
                    "form": self.get_form(),
                    "error": "Too many requests. Try again later.",
                },
                status=429,
            )
        return super().post(request, *args, **kwargs)
