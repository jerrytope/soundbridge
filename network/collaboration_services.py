from decimal import Decimal, InvalidOperation
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from network.models import (
    Collaboration,
    Participant,
    SplitRound,
    SplitResponse,
    CollaborationMessage,
    CollaborationPreference,
)
from network.services import blocked
from operations.services import audit, notify


def require_access(user, project, owner_only=False):
    if user.pk == project.owner_id:
        return
    if (
        owner_only
        or blocked(user, project.owner)
        or not project.participants.filter(
            user=user, invitation_state="accepted"
        ).exists()
    ):
        raise PermissionDenied


def require_group_message(user, project):
    require_access(user, project)
    members = [project.owner] + [
        p.user
        for p in project.participants.select_related("user").filter(
            invitation_state="accepted", user__isnull=False
        )
    ]
    if any(member.pk != user.pk and blocked(user, member) for member in members):
        raise PermissionDenied


@transaction.atomic
def invitation_response(user, participant, action):
    participant = (
        Participant.objects.select_for_update()
        .select_related("collaboration")
        .get(pk=participant.pk)
    )
    if participant.user_id != user.pk:
        raise PermissionDenied
    if blocked(user, participant.collaboration.owner):
        raise PermissionDenied
    desired = {"accept": "accepted", "decline": "declined"}.get(action)
    if desired is None:
        raise ValidationError("Choose accept or decline.")
    if participant.invitation_state == desired:
        return
    if participant.expires_at and participant.expires_at <= timezone.now():
        raise ValidationError("This invitation expired.")
    if participant.invitation_state != "pending":
        raise ValidationError("This invitation is no longer pending.")
    participant.invitation_state = desired
    participant.save(update_fields=["invitation_state"])
    audit(user, "collaboration.invitation." + desired, participant)
    notify(
        participant.collaboration.owner,
        "collaborations",
        "Collaboration invitation " + desired,
        f"/collaborations/{participant.collaboration_id}",
        f"invitation:{participant.pk}:{desired}",
    )


@transaction.atomic
def propose_splits(user, project, shares):
    project = Collaboration.objects.select_for_update().get(pk=project.pk)
    require_access(user, project, owner_only=True)
    allowed = {str(project.owner_id)} | {
        str(pk)
        for pk in project.participants.filter(
            invitation_state="accepted", user__isnull=False
        ).values_list("user_id", flat=True)
    }
    if set(shares) != allowed:
        raise ValidationError(
            "Include the owner and each accepted participant exactly once."
        )
    try:
        values = {key: Decimal(value) for key, value in shares.items()}
        if (
            any(
                not value.is_finite()
                or value < 0
                or value > 100
                or value.as_tuple().exponent < -4
                for value in values.values()
            )
            or sum(values.values()) != 100
        ):
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(
            "Split shares must be finite percentages with at most four decimals totaling 100."
        )
    version = (project.split_rounds.aggregate(v=Max("version"))["v"] or 0) + 1
    proposal = SplitRound.objects.create(
        collaboration=project,
        version=version,
        shares={key: str(value) for key, value in values.items()},
    )
    audit(user, "split.proposed", proposal)
    return proposal


@transaction.atomic
def respond_split(user, proposal, response):
    project = Collaboration.objects.select_for_update().get(
        pk=proposal.collaboration_id
    )
    require_access(user, project)
    proposal = SplitRound.objects.select_for_update().get(pk=proposal.pk)
    if str(user.pk) not in proposal.shares:
        raise PermissionDenied
    if project.split_rounds.order_by("-version").first().pk != proposal.pk:
        raise ValidationError("A newer split proposal exists.")
    if response not in ("acknowledged", "disputed"):
        raise ValidationError("Choose acknowledge or dispute.")
    existing = SplitResponse.objects.filter(proposal=proposal, user=user).first()
    if existing:
        if existing.response != response:
            raise ValidationError(
                "Your response is recorded. Ask the owner for a revised proposal."
            )
        return
    SplitResponse.objects.create(proposal=proposal, user=user, response=response)
    responses = list(proposal.responses.values_list("response", flat=True))
    proposal.state = (
        "disputed"
        if "disputed" in responses
        else "acknowledged"
        if len(responses) == len(proposal.shares)
        else "proposed"
    )
    proposal.save(update_fields=["state"])
    audit(user, "split." + response, proposal)


@transaction.atomic
def message(user, project, body, client_id):
    project = Collaboration.objects.select_for_update().get(pk=project.pk)
    require_group_message(user, project)
    if not body.strip() or len(body) > 8000:
        raise ValidationError("Enter a message of 1–8000 characters.")
    row, created = CollaborationMessage.objects.get_or_create(
        sender=user,
        client_id=client_id,
        defaults={"collaboration": project, "body": body.strip()},
    )
    if row.collaboration_id != project.pk or row.body != body.strip():
        raise ValidationError("This retry key was already used for another message.")
    if created:
        audit(user, "collaboration.message.sent", row)
        members = [project.owner] + [p.user for p in project.participants.select_related("user").filter(invitation_state="accepted", user__isnull=False)]
        muted = set(CollaborationPreference.objects.filter(collaboration=project, muted=True).values_list("user_id", flat=True))
        for member in members:
            if member.pk != user.pk and member.pk not in muted:
                notify(member, "messages", "New collaboration message", f"/collaborations/{project.pk}", f"group-message:{row.pk}")
    return row
