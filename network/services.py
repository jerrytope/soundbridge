from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from accounts.models import User
from accounts.security import verified
from network.models import CreatorConnection, UserBlock, DirectMessage, ThreadPreference
from operations.services import audit, notify


def blocked(first, second):
    return UserBlock.objects.filter(
        Q(owner=first, target=second) | Q(owner=second, target=first)
    ).exists()


def _lock_users(first, second):
    # A deterministic lock order also serializes reverse-direction requests and blocks.
    list(
        User.objects.select_for_update()
        .filter(pk__in=[party.pk for party in (first, second) if party is not None])
        .order_by("pk")
    )


def both_parties(connection):
    """False once an account on this connection has been deleted."""
    return connection.requester_id is not None and connection.recipient_id is not None


@transaction.atomic
def request_connection(sender, recipient):
    _lock_users(sender, recipient)
    if sender.pk == recipient.pk or blocked(sender, recipient):
        raise PermissionDenied
    if (
        not verified(sender)
        or not verified(recipient)
        or not recipient.is_active
        or not recipient.profile.published
    ):
        raise PermissionDenied
    from billing.services import EntitlementRequired, check
    from django.utils import timezone

    try:
        check(
            sender,
            "connection_requests_daily",
            CreatorConnection.objects.filter(
                requester=sender, created_at__date=timezone.now().date()
            ).count(),
            "Connection requests a day",
        )
    except EntitlementRequired as limited:
        raise ValidationError(limited.message)
    key = ":".join(sorted([str(sender.pk), str(recipient.pk)]))
    connection, created = CreatorConnection.objects.get_or_create(
        pair_key=key, defaults={"requester": sender, "recipient": recipient}
    )
    if not created:
        if connection.state in ("pending", "accepted"):
            return connection
        raise ValidationError("This request is closed. You cannot send it again.")
    audit(sender, "connection.requested", connection)
    notify(
        recipient,
        "connections",
        "New connection request",
        "/connections",
        f"connection:{connection.pk}",
    )
    return connection


@transaction.atomic
def transition_connection(actor, connection, action):
    _lock_users(connection.requester, connection.recipient)
    connection = CreatorConnection.objects.select_for_update().get(pk=connection.pk)
    if not both_parties(connection):
        raise PermissionDenied
    if actor.pk not in (connection.requester_id, connection.recipient_id):
        raise PermissionDenied
    if blocked(connection.requester, connection.recipient):
        raise PermissionDenied
    target = {"accept": "accepted", "decline": "declined", "cancel": "cancelled"}.get(
        action
    )
    permitted = actor.pk == (
        connection.requester_id if action == "cancel" else connection.recipient_id
    )
    if not target or not permitted:
        raise PermissionDenied
    if connection.state == target:
        return connection
    if connection.state != "pending":
        raise ValidationError("This connection request is no longer pending.")
    connection.state = target
    connection.save(update_fields=["state", "updated_at"])
    audit(actor, f"connection.{target}", connection)
    other = (
        connection.recipient
        if actor.pk == connection.requester_id
        else connection.requester
    )
    notify(
        other,
        "connections",
        f"Connection request {target}",
        "/connections",
        f"connection:{connection.pk}:{target}",
    )
    return connection


@transaction.atomic
def block_user(owner, target):
    if owner.pk == target.pk:
        raise ValidationError("You cannot block yourself.")
    _lock_users(owner, target)
    block, created = UserBlock.objects.get_or_create(owner=owner, target=target)
    CreatorConnection.objects.filter(
        Q(requester=owner, recipient=target) | Q(requester=target, recipient=owner)
    ).update(state="blocked")
    if created:
        audit(owner, "user.blocked", block)


def require_thread(user, connection, reading=False):
    """Membership check for a thread. Reading survives the other account's deletion."""
    if (
        user.pk not in (connection.requester_id, connection.recipient_id)
        or connection.state != "accepted"
    ):
        raise PermissionDenied
    if not both_parties(connection):
        if not reading:
            raise PermissionDenied
        return
    if blocked(connection.requester, connection.recipient):
        raise PermissionDenied


@transaction.atomic
def send_message(user, connection, body, client_id):
    _lock_users(connection.requester, connection.recipient)
    connection.refresh_from_db()
    require_thread(user, connection)
    body = body.strip()
    if not body or len(body) > 8000:
        raise ValidationError("Enter a message of 1–8000 characters.")
    message, created = DirectMessage.objects.get_or_create(
        sender=user,
        client_id=client_id,
        defaults={"connection": connection, "body": body},
    )
    if message.connection_id != connection.pk or message.body != body:
        raise ValidationError(
            "This message retry key was already used for different content."
        )
    if created:
        audit(user, "message.sent", message)
        other = (
            connection.recipient
            if user.pk == connection.requester_id
            else connection.requester
        )
        if not ThreadPreference.objects.filter(
            user=other, connection=connection, muted=True
        ).exists():
            notify(
                other,
                "messages",
                "New message",
                f"/messages/{connection.pk}",
                f"message:{message.pk}",
            )
    return message
