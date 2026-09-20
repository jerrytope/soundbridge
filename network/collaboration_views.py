import uuid
from datetime import timedelta
from pathlib import Path
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from accounts.models import User
from accounts.security import verified_filter
from network.models import Collaboration, Participant, Milestone, CollaborationFile
from network.collaboration_services import (
    require_access,
    require_group_message,
    invitation_response,
    propose_splits,
    respond_split,
    message,
)
from network.models import CollaborationPreference, Report
from apiv1.limits import limit_request, RateLimited
from network.services import blocked
from operations.services import audit, notify


class BriefForm(forms.ModelForm):
    class Meta:
        model = Collaboration
        fields = [
            "title",
            "brief",
            "role_needed",
            "genre",
            "budget_visible",
            "budget_amount",
            "budget_currency",
            "starts_on",
            "ends_on",
            "state",
        ]
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        data = super().clean()
        if data.get("budget_amount") is not None:
            if data["budget_amount"] < 0:
                self.add_error("budget_amount", "Budget cannot be negative.")
            if not data.get("budget_currency"):
                self.add_error("budget_currency", "Choose a currency for the budget.")
        if (
            data.get("starts_on")
            and data.get("ends_on")
            and data["starts_on"] > data["ends_on"]
        ):
            self.add_error("ends_on", "End date precedes start date.")
        return data


@login_required
@require_http_methods(["GET", "POST"])
def workspace(request, project_id):
    project = get_object_or_404(Collaboration, pk=project_id)
    require_access(request.user, project)
    owner = request.user.pk == project.owner_id
    form = BriefForm(
        request.POST if request.POST.get("action") == "brief" else None,
        instance=project,
    )
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            with transaction.atomic():
                project = Collaboration.objects.select_for_update().get(pk=project.pk)
                require_access(request.user, project)
                if action == "brief":
                    require_access(request.user, project, True)
                    if form.is_valid():
                        obj = form.save(commit=False)
                        obj.done = obj.state == "completed"
                        obj.save()
                        audit(request.user, "collaboration.updated", obj)
                    else:
                        raise ValidationError("Please correct the brief fields below.")
                elif action == "invite":
                    require_access(request.user, project, True)
                    target = get_object_or_404(
                        User,
                        verified_filter(),
                        profile__username=request.POST.get("username"),
                        profile__published=True,
                        is_active=True,
                    )
                    if target.pk == project.owner_id or blocked(request.user, target):
                        raise ValidationError("This creator cannot be invited.")
                    if not project.participants.filter(user=target).exists():
                        item = Participant.objects.create(
                            collaboration=project,
                            user=target,
                            display_name=target.profile.name,
                            role=request.POST.get("role", "")[:120],
                            expires_at=timezone.now() + timedelta(days=7),
                        )
                        audit(request.user, "collaboration.invited", item)
                        notify(
                            target,
                            "collaborations",
                            "Collaboration invitation",
                            "/collaborations/invitations",
                            f"invite:{item.pk}",
                        )
                elif action == "remove-participant":
                    require_access(request.user, project, True)
                    item = get_object_or_404(
                        project.participants, pk=request.POST.get("id")
                    )
                    item.invitation_state = "expired"
                    item.save(update_fields=["invitation_state"])
                    audit(request.user, "collaboration.access.removed", item)
                elif action == "milestone":
                    require_access(request.user, project, True)
                    title = request.POST.get("title", "").strip()
                    if not title or len(title) > 300:
                        raise ValidationError(
                            "Enter a milestone title up to 300 characters."
                        )
                    due = forms.DateField(required=False).clean(
                        request.POST.get("due_date")
                    )
                    assignee = (
                        get_object_or_404(
                            project.participants,
                            pk=request.POST["participant"],
                            invitation_state="accepted",
                        )
                        if request.POST.get("participant")
                        else None
                    )
                    item = Milestone.objects.create(
                        collaboration=project,
                        title=title,
                        due_date=due,
                        participant=assignee,
                        assignee=assignee.display_name if assignee else "",
                    )
                    audit(request.user, "milestone.created", item)
                elif action == "milestone-state":
                    item = get_object_or_404(
                        project.milestones, pk=request.POST.get("id")
                    )
                    if not owner and (
                        not item.participant_id
                        or item.participant.user_id != request.user.pk
                    ):
                        raise ValidationError(
                            "Only the owner or assignee can update this milestone."
                        )
                    state = request.POST.get("state")
                    if state not in dict(Milestone.STATES):
                        raise ValidationError("Choose a valid milestone state.")
                    item.state = state
                    item.notes = request.POST.get("notes", "")[:4000]
                    item.save()
                    audit(request.user, "milestone.updated", item)
                elif action == "mute":
                    CollaborationPreference.objects.update_or_create(user=request.user, collaboration=project, defaults={"muted": request.POST.get("muted") == "on"})
                elif action == "report-message":
                    require_group_message(request.user, project)
                    item = get_object_or_404(project.messages, pk=request.POST.get("id"))
                    reason = forms.CharField(max_length=4000).clean(request.POST.get("reason"))
                    limit_request(f"report:{request.user.pk}", 5, 3600)
                    row = Report.objects.create(reporter=request.user, target_user=item.sender, collaboration_message=item, reason=reason)
                    audit(request.user, "report.created", row)
                    messages.success(request, "Message report received for review.")
                elif action == "message":
                    limit_request(f"message:{request.user.pk}", 30)
                    message(
                        request.user,
                        project,
                        request.POST.get("body", ""),
                        uuid.UUID(request.POST.get("client_id", "")),
                    )
                elif action == "split":
                    shares = {
                        key.removeprefix("share_"): value
                        for key, value in request.POST.items()
                        if key.startswith("share_")
                    }
                    propose_splits(request.user, project, shares)
                elif action == "split-response":
                    respond_split(
                        request.user,
                        get_object_or_404(
                            project.split_rounds, pk=request.POST.get("id")
                        ),
                        request.POST.get("response"),
                    )
                elif action == "file":
                    require_group_message(request.user, project)
                    file = request.FILES.get("file")
                    if (
                        not file
                        or file.size > 5 * 1024 * 1024
                        or Path(file.name).suffix.lower()
                        not in (".pdf", ".txt", ".png", ".jpg", ".jpeg", ".mp3", ".wav")
                    ):
                        raise ValidationError(
                            "Upload a PDF, text, image or audio file up to 5 MB."
                        )
                    if project.files.count() >= 100:
                        raise ValidationError(
                            "This project has reached its 100-file limit."
                        )
                    item = CollaborationFile.objects.create(
                        collaboration=project,
                        uploader=request.user,
                        name=Path(file.name).name[:200],
                        content=file.read(),
                    )
                    audit(request.user, "collaboration.file.quarantined", item)
                else:
                    raise ValidationError("Unknown action.")
            return redirect(request.path)
        except (ValidationError, ValueError, RateLimited) as error:
            messages.error(request, str(error))
    participants = project.participants.select_related("user", "collaboration")
    parties = [{"id": str(project.owner_id), "name": project.owner.profile.name}] + [
        {"id": str(p.user_id), "name": p.display_name}
        for p in participants
        if p.user_id and p.invitation_state == "accepted"
    ]
    from operations.models import AuditEvent

    resource_ids = (
        [str(project.pk)]
        + [str(pk) for pk in project.milestones.values_list("pk", flat=True)]
        + [str(pk) for pk in participants.values_list("pk", flat=True)]
    )
    activity = AuditEvent.objects.filter(
        resource_id__in=resource_ids,
        resource_type__in=[
            "network.collaboration",
            "network.milestone",
            "network.participant",
        ],
    )[:50]
    try:
        require_group_message(request.user, project)
        visible_messages = project.messages.select_related("sender").order_by(
            "-created_at"
        )
    except PermissionDenied:
        visible_messages = project.messages.none()
    return render(
        request,
        "network/collaboration.html",
        {
            "project": project,
            "muted": CollaborationPreference.objects.filter(user=request.user, collaboration=project, muted=True).exists(),
            "form": form,
            "is_owner": owner,
            "participants": participants,
            "parties": parties,
            "milestone_states": Milestone.STATES,
            "page_obj": Paginator(visible_messages, 30).get_page(
                request.GET.get("page")
            ),
            "client_id": uuid.uuid4(),
            "activity": activity,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def invitations(request):
    if request.method == "POST":
        item = get_object_or_404(
            Participant, pk=request.POST.get("id"), user=request.user
        )
        try:
            invitation_response(request.user, item, request.POST.get("action"))
        except ValidationError as error:
            messages.error(request, error.messages[0])
        return redirect(request.path)
    request.user.collaboration_invitations.filter(
        invitation_state="pending", expires_at__lte=timezone.now()
    ).update(invitation_state="expired")
    return render(
        request,
        "network/invitations.html",
        {
            "invitations": request.user.collaboration_invitations.select_related(
                "collaboration"
            ).order_by("-invited_at")
        },
    )


@login_required
def file_download(request, file_id):
    row = get_object_or_404(CollaborationFile, pk=file_id, state="clean")
    require_group_message(request.user, row.collaboration)
    response = HttpResponse(bytes(row.content), content_type="application/octet-stream")
    from django.utils.http import content_disposition_header

    response["Content-Disposition"] = content_disposition_header(True, row.name)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    return response
