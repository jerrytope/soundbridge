import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from accounts.models import Consent
from operations.models import NotificationPreference, PrivacyRequest
from operations.services import audit

CATEGORIES = [
    ("connections", "Connections"),
    ("messages", "Messages"),
    ("collaborations", "Collaborations"),
    ("releases", "Release reminders"),
    ("opportunities", "Opportunity deadlines"),
]


@login_required
@require_http_methods(["GET", "POST"])
def notifications(request):
    if request.method == "POST":
        if request.POST.get("action") == "read":
            request.user.notifications.filter(pk=request.POST.get("id")).update(
                read_at=timezone.now()
            )
        else:
            for key, _ in CATEGORIES:
                NotificationPreference.objects.update_or_create(
                    user=request.user,
                    category=key,
                    defaults={
                        "email": request.POST.get(key + "_email") == "on",
                        "in_app": request.POST.get(key + "_app") == "on",
                    },
                )
        return redirect("/notifications")
    preferences = []
    for key, label in CATEGORIES:
        row = NotificationPreference.objects.filter(
            user=request.user, category=key
        ).first()
        preferences.append(
            {
                "key": key,
                "label": label,
                "email": bool(row and row.email),
                "in_app": row is None or row.in_app,
            }
        )
    return render(
        request,
        "operations/notifications.html",
        {
            "preferences": preferences,
            "page_obj": Paginator(
                request.user.notifications.order_by("-created_at"), 30
            ).get_page(request.GET.get("page")),
        },
    )


def workspace_export(user):
    """Portable JSON of owned data; no passwords, tokens, or third-party private profiles."""
    from apiv1.serializers import workspace_for
    from accounts.models import StoredImage
    from network.models import (
        CreatorConnection,
        DirectMessage,
        Report,
        SavedOpportunity,
    )
    from django.db.models import Q
    import base64

    payload = {
        "schema_version": "soundbridge-export-2",
        "generated_at": timezone.now(),
        "account": {
            "id": user.pk,
            "email": user.email,
            "email_verified_at": user.email_verified_at,
            "timezone": user.timezone,
        },
        "workspace": workspace_for(user),
    }
    payload["profile"] = model_to_dict(user.profile)
    payload["manual_income"] = list(user.manual_income.values())
    payload["calculations"] = list(user.calculations.values())
    payload["imports"] = list(
        user.import_batches.values(
            "id", "name", "state", "mapping", "columns", "error", "created_at"
        )
    )
    payload["collaboration_invitations"] = list(user.collaboration_invitations.values())
    from network.models import CollaborationMessage, SplitResponse

    payload["authored_collaboration_messages"] = list(
        CollaborationMessage.objects.filter(sender=user).values()
    )
    payload["split_responses"] = list(SplitResponse.objects.filter(user=user).values())
    payload["credits"] = list(user.profile.credits.values())
    payload["links"] = list(user.profile.links.values())
    payload["consents"] = list(user.consents.values())
    payload["notifications"] = list(user.notifications.values())
    payload["notification_preferences"] = list(
        NotificationPreference.objects.filter(user=user).values()
    )
    payload["connections"] = list(
        CreatorConnection.objects.filter(Q(requester=user) | Q(recipient=user)).values()
    )
    # Export authored messages. Other participants' content needs the approved sharing policy.
    payload["authored_messages"] = list(
        DirectMessage.objects.filter(sender=user).values()
    )
    payload["blocks"] = list(user.blocks.values())
    payload["reports"] = list(
        Report.objects.filter(reporter=user).values(
            "id", "target_user_id", "opportunity_id", "reason", "state", "created_at"
        )
    )
    payload["saved_opportunities"] = list(
        SavedOpportunity.objects.filter(user=user).values()
    )
    payload["images"] = [
        {
            "id": str(row.pk),
            "content_type": "image/jpeg",
            "base64": base64.b64encode(row.data()).decode(),
        }
        for row in StoredImage.objects.filter(user=user)
    ]
    payload["statement_originals"] = [
        {
            "id": str(row.pk),
            "base64": base64.b64encode(row.original_bytes()).decode()
            if row.original_bytes()
            else None,
        }
        for row in user.statements.all()
    ]
    payload["royalty_transactions"] = [
        list(row.transactions.values()) for row in user.statements.all()
    ]
    return payload


@login_required
@require_http_methods(["GET", "POST"])
def privacy(request):
    class PrivacyForm(forms.Form):
        password = forms.CharField(widget=forms.PasswordInput, label="Current password")
        action = forms.ChoiceField(
            choices=[
                ("export", "Download my data"),
                ("deletion", "Request account deletion"),
                ("revoke-ai", "Revoke AI context consent"),
            ]
        )

    form = PrivacyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from accounts.security import throttle
        from apiv1.limits import RateLimited

        try:
            throttle(request, request.user.email, "privacy")
        except RateLimited:
            form.add_error(None, "Too many attempts. Try again later.")
        else:
            if not request.user.check_password(form.cleaned_data["password"]):
                form.add_error("password", "Password is incorrect.")
            else:
                action = form.cleaned_data["action"]
                if action == "revoke-ai":
                    Consent.objects.create(
                        user=request.user,
                        purpose="ai-context",
                        version="1",
                        granted=False,
                    )
                    request.user.ai_conversations.update(context={}, handoff=None)
                    from aiteam.models import ContextPreference

                    ContextPreference.objects.filter(user=request.user).update(
                        profile=False, brief=False, releases=False, royalties=False
                    )
                    messages.success(
                        request,
                        "AI context consent revoked. Stored context snapshots cleared.",
                    )
                    return redirect("/settings/privacy")
                if action == "deletion":
                    row, _ = PrivacyRequest.objects.get_or_create(
                        user=request.user, kind="deletion", state="pending"
                    )
                    audit(request.user, "privacy.deletion.requested", row)
                    messages.info(
                        request,
                        "Deletion request recorded. Processing follows the approved retention and shared-data policy; no completion date has been promised.",
                    )
                    return redirect("/settings/privacy")
                row = PrivacyRequest.objects.create(user=request.user, kind="export")
                response = HttpResponse(
                    json.dumps(
                        workspace_export(request.user), cls=DjangoJSONEncoder, indent=2
                    ),
                    content_type="application/json",
                )
                response["Content-Disposition"] = (
                    'attachment; filename="soundbridge-export.json"'
                )
                response["Cache-Control"] = "no-store"
                row.state = "completed"
                row.completed_at = timezone.now()
                row.save()
                audit(request.user, "privacy.export.completed", row)
                return response
    from operations import privacy as privacy_service

    return render(
        request,
        "operations/privacy.html",
        {
            "form": form,
            "requests": request.user.privacy_requests.order_by("-created_at"),
            "consents": request.user.consents.order_by("-created_at"),
            "exports": request.user.artifacts.filter(kind="privacy-export"),
            "policy": privacy_service.policy(),
            "now": timezone.now(),
        },
    )

@login_required
def download_artifact(request, artifact_id):
    """Serve a private artifact to its owner.

    The signed `token` link is accepted as well, so a short-lived link can be
    sent to the account holder; it still has to be the owner's session behind
    it, and an expired artifact is gone rather than merely hidden.
    """
    from django.core.exceptions import PermissionDenied
    from django.http import Http404
    from operations import storage
    from operations.models import PrivateArtifact

    artifact = get_object_or_404(PrivateArtifact, pk=artifact_id, user=request.user)
    if storage.expired(artifact):
        raise Http404("This file has expired.")
    token = request.GET.get("token")
    if token:
        try:
            storage.check_token(artifact, token, request.GET.get("ttl", 900))
        except PermissionDenied as problem:
            raise Http404(str(problem))
    try:
        data = storage.read(artifact)
    except FileNotFoundError:
        raise Http404("This file is no longer stored.")
    artifact.downloaded_at = timezone.now()
    artifact.save(update_fields=["downloaded_at"])
    audit(request.user, "privacy.export.downloaded", artifact)
    response = HttpResponse(data, content_type=artifact.content_type)
    response["Content-Disposition"] = f'attachment; filename="{artifact.filename}"'
    response["Cache-Control"] = "no-store"
    return response



def legal(request, document):
    if document not in ("terms", "privacy"):
        from django.http import Http404

        raise Http404
    # Do not invent legal copy. Operators must provide approved text before public registration.
    from operations.models import LaunchDecision

    key = "terms-copy" if document == "terms" else "privacy-copy"
    decision = LaunchDecision.objects.filter(key=key, approved_at__isnull=False).first()
    return render(
        request,
        "operations/legal.html",
        {"document": document.title(), "decision": decision},
    )
