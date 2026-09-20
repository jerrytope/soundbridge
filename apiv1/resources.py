"""Versioned resource API. Templates and JSON commands call the same domain services."""

import hashlib
import json
import uuid
from functools import wraps
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from accounts.models import User
from operations.models import MutationReceipt
from operations.services import audit
from apiv1.limits import limit_request, RateLimited


def error(code, message, status):
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def endpoint(methods):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return error("authentication_required", "Sign in to continue.", 401)
            if request.method not in methods:
                return error("method_not_allowed", "Unsupported method.", 405)
            try:
                if request.method == "GET":
                    payload, status = view(request, {}, *args, **kwargs)
                else:
                    # A DELETE carries no body, so it carries no content type.
                    body_expected = request.method != "DELETE" or request.body
                    if body_expected and not (request.content_type or "").startswith(
                        "application/json"
                    ):
                        return error("content_type", "Send application/json.", 415)
                    if len(request.body) > 131072:
                        return error("body_too_large", "Request exceeds 128 KiB.", 413)
                    data = json.loads(request.body or "{}")
                    if not isinstance(data, dict):
                        return error("invalid_body", "Send a JSON object.", 400)
                    try:
                        key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
                    except ValueError:
                        return error(
                            "idempotency_key",
                            "Send a UUID Idempotency-Key header.",
                            400,
                        )
                    fingerprint = hashlib.sha256(
                        (
                            request.method
                            + request.path
                            + json.dumps(data, sort_keys=True, separators=(",", ":"))
                        ).encode()
                    ).hexdigest()
                    with transaction.atomic():
                        receipt, created = MutationReceipt.objects.get_or_create(
                            user=request.user,
                            key=key,
                            defaults={
                                "fingerprint": fingerprint,
                                "payload": {},
                                "status": 200,
                            },
                        )
                        if not created:
                            if receipt.fingerprint != fingerprint:
                                return error(
                                    "idempotency_conflict",
                                    "This key was used for another command.",
                                    409,
                                )
                            return JsonResponse(receipt.payload, status=receipt.status)
                        limit_request(f"v1:{request.user.pk}", 60)
                        payload, status = view(request, data, *args, **kwargs)
                        encoded = json.loads(json.dumps(payload, cls=DjangoJSONEncoder))
                        receipt.payload = encoded
                        receipt.status = status
                        receipt.save(update_fields=["payload", "status"])
                response = JsonResponse(payload, status=status)
                response["Cache-Control"] = "no-store"
                return response
            except Http404:
                return error("not_found", "Resource not found.", 404)
            except PermissionDenied:
                return error("forbidden", "You cannot perform this action.", 403)
            except (ValidationError, ValueError, TypeError) as problem:
                return error("validation", str(problem), 400)
            except IntegrityError:
                return error(
                    "conflict", "This command conflicts with an existing record.", 409
                )
            except RateLimited:
                return error("rate_limited", "Too many requests. Try again later.", 429)

        return wrapped

    return decorate


def records(request, queryset, fields):
    page = Paginator(queryset, 20).get_page(request.GET.get("page"))
    return {
        "data": list(page.object_list.values(*fields)),
        "pagination": {
            "page": page.number,
            "pages": page.paginator.num_pages,
            "count": page.paginator.count,
        },
    }, 200


@endpoint(["GET", "PUT"])
def profile(request, data):
    from accounts.forms import ProfileForm

    row = request.user.profile
    if request.method == "PUT":
        form = ProfileForm(data, instance=row)
        if not form.is_valid():
            raise ValidationError(form.errors.as_json())
        form.save()
        audit(request.user, "profile.updated", row)
    fields = [
        "name",
        "username",
        "role",
        "country",
        "city",
        "bio",
        "skills",
        "genres",
        "goals",
        "availability",
        "published",
        "city_public",
        "portfolio_public",
        "photo_public",
        "availability_public",
        "portfolio",
    ]
    return {"data": {key: getattr(row, key) for key in fields}}, 200


@endpoint(["GET", "POST"])
def connections(request, data):
    from network.models import CreatorConnection
    from network.services import request_connection

    if request.method == "POST":
        row = request_connection(
            request.user, get_object_or_404(User, pk=data.get("recipient"))
        )
        return {"data": {"id": str(row.pk), "state": row.state}}, 201
    return records(
        request,
        CreatorConnection.objects.filter(
            Q(requester=request.user) | Q(recipient=request.user)
        ).order_by("-created_at"),
        ["id", "requester_id", "recipient_id", "state", "created_at", "updated_at"],
    )


@endpoint(["POST"])
def connection_action(request, data, connection_id):
    from network.models import CreatorConnection
    from network.services import transition_connection

    row = transition_connection(
        request.user,
        get_object_or_404(CreatorConnection, pk=connection_id),
        data.get("action"),
    )
    return {"data": {"id": str(row.pk), "state": row.state}}, 200


@endpoint(["GET", "POST"])
def messages(request, data, connection_id):
    from network.models import CreatorConnection
    from network.services import require_thread, send_message

    row = get_object_or_404(CreatorConnection, pk=connection_id)
    require_thread(request.user, row)
    if request.method == "POST":
        message = send_message(
            request.user,
            row,
            str(data.get("body", "")),
            uuid.UUID(request.headers["Idempotency-Key"]),
        )
        return {"data": {"id": str(message.pk)}}, 201
    return records(
        request,
        row.messages.order_by("-created_at", "-pk"),
        ["id", "sender_id", "body", "created_at"],
    )


@endpoint(["GET", "POST"])
def calculations(request, data):
    from royalties.models import Calculation
    from royalties.forms import ScenarioForm
    from royalties.scenarios import save_scenario

    if request.method == "POST":
        form = ScenarioForm(data)
        if not form.is_valid():
            raise ValidationError(form.errors.as_json())
        row = save_scenario(request.user, form.cleaned_data)
        return {
            "data": {
                "id": str(row.pk),
                "currency": row.currency,
                "assumptions": row.assumptions,
            }
        }, 201
    return records(
        request,
        Calculation.objects.filter(owner=request.user).order_by("-created_at"),
        [
            "id",
            "platform",
            "currency",
            "amount",
            "rate_source",
            "rate_effective_date",
            "rate_version",
            "formula",
            "assumptions",
        ],
    )


@endpoint(["GET", "POST"])
def releases(request, data):
    from releases.models import ReleaseProject
    from releases.detail_views import ReleaseForm
    from releases.models import CHECKLIST, ReleaseTask

    if request.method == "POST":
        row = ReleaseProject(owner=request.user)
        form = ReleaseForm(data, instance=row)
        if not form.is_valid():
            raise ValidationError(form.errors.as_json())
        form.save()
        ReleaseTask.objects.bulk_create(
            [
                ReleaseTask(release=row, title=title, position=index)
                for index, title in enumerate(CHECKLIST)
            ]
        )
        audit(request.user, "release.created", row)
        return {"data": {"id": str(row.pk)}}, 201
    return records(
        request,
        ReleaseProject.objects.filter(owner=request.user).order_by("-created_at"),
        [
            "id",
            "title",
            "type",
            "date",
            "stage",
            "support_needs",
            "metadata_ready",
            "campaign_plan",
            "reminders_enabled",
        ],
    )


@endpoint(["GET", "POST"])
def income(request, data):
    from royalties.models import ManualIncome
    from royalties.forms import ManualIncomeForm

    if request.method == "POST":
        form = ManualIncomeForm(data)
        if not form.is_valid():
            raise ValidationError(form.errors.as_json())
        row = form.save(commit=False)
        row.owner = request.user
        row.save()
        audit(request.user, "income.saved", row)
        return {"data": {"id": str(row.pk)}}, 201
    return records(
        request,
        ManualIncome.objects.filter(owner=request.user).order_by("-date", "pk"),
        [
            "id",
            "source",
            "work",
            "platform",
            "territory",
            "date",
            "category",
            "currency",
            "amount",
            "note",
        ],
    )


@endpoint(["GET"])
def notifications(request, data):
    return records(
        request,
        request.user.notifications.order_by("-created_at"),
        ["id", "category", "title", "url", "read_at", "created_at"],
    )


@endpoint(["GET"])
def statements(request, data):
    return records(
        request,
        request.user.statements.order_by("-created_at"),
        [
            "id",
            "name",
            "source",
            "period_start",
            "period_end",
            "processing_state",
            "schema_version",
            "created_at",
        ],
    )


@endpoint(["GET"])
def statement_rows(request, data, statement_id):
    row = get_object_or_404(request.user.statements, pk=statement_id)
    from royalties.imports import FIELDS

    return records(request, row.transactions.order_by("position"), ["id"] + FIELDS)


@endpoint(["GET", "PUT"])
def goals(request, data):
    """The career goals onboarding collects. Up to three, as the screens allow."""
    from accounts.models import GOALS

    profile = request.user.profile
    if request.method == "PUT":
        chosen = data.get("goals")
        if not isinstance(chosen, list) or len(chosen) > 3:
            raise ValidationError("Send a list of up to three goals.")
        unknown = [item for item in chosen if item not in GOALS]
        if unknown:
            raise ValidationError(f"Unknown goal: {unknown[0]}")
        profile.goals = chosen
        profile.save(update_fields=["goals", "updated_at"])
        audit(request.user, "goals.updated", profile)
    return {"data": {"goals": profile.goals, "available": GOALS}}, 200


@endpoint(["GET", "POST"])
def credits(request, data):
    """Credits on the creator profile. Verification state is never self-assigned."""
    from accounts.forms import CreditForm

    profile = request.user.profile
    if request.method == "POST":
        form = CreditForm(data)
        if not form.is_valid():
            raise ValidationError(form.errors.as_json())
        row = form.save(commit=False)
        row.profile = profile
        row.save()
        audit(request.user, "credit.added", row)
        return {
            "data": {"id": row.pk, "verification_state": row.verification_state}
        }, 201
    return records(
        request,
        profile.credits.order_by("-id"),
        ["id", "work", "role", "source", "date", "verification_state"],
    )


@endpoint(["GET", "POST"])
def collaborations(request, data):
    from network.models import Collaboration

    if request.method == "POST":
        title = str(data.get("title", "")).strip()
        brief = str(data.get("brief", "")).strip()
        if not title or not brief:
            raise ValidationError("A collaboration needs a title and a brief.")
        from billing.services import EntitlementRequired, check

        try:
            check(
                request.user,
                "active_collaborations",
                Collaboration.objects.filter(owner=request.user)
                .exclude(state__in=[Collaboration.COMPLETED, Collaboration.CANCELLED])
                .count(),
                "Active collaborations",
            )
        except EntitlementRequired as limited:
            return {"error": {"code": "entitlement", "message": limited.message}}, 402
        row = Collaboration.objects.create(
            owner=request.user,
            title=title[:300],
            brief=brief[:4000],
            role_needed=str(data.get("role_needed", ""))[:120],
            genre=str(data.get("genre", ""))[:120],
            state=Collaboration.DRAFT,
        )
        audit(request.user, "collaboration.created", row)
        return {"data": {"id": str(row.pk), "state": row.state}}, 201
    owned = Q(owner=request.user)
    joined = Q(
        participants__user=request.user, participants__invitation_state="accepted"
    )
    return records(
        request,
        Collaboration.objects.filter(owned | joined).distinct().order_by("-created_at"),
        ["id", "title", "brief", "role_needed", "genre", "state", "done", "created_at"],
    )


@endpoint(["GET"])
def opportunities(request, data):
    """The curated directory: verified rows only, with the evidence behind them."""
    from network.models import Opportunity

    rows = Opportunity.objects.filter(verification_state=Opportunity.VERIFIED)
    kind = request.GET.get("type")
    if kind:
        rows = rows.filter(type=kind)
    return records(
        request,
        rows.order_by("deadline", "id"),
        [
            "id",
            "slug",
            "title",
            "type",
            "city",
            "description",
            "source",
            "eligibility",
            "deadline",
            "cost",
            "url",
            "verification_state",
        ],
    )


@endpoint(["GET", "DELETE"])
def ai_conversations(request, data):
    """List conversations, or delete every one of them on request."""
    rows = request.user.ai_conversations.order_by("-created_at")
    if request.method == "DELETE":
        count = rows.count()
        for row in rows:
            audit(request.user, "ai.conversation.deleted", row)
        rows.delete()
        return {"data": {"deleted": count}}, 200
    return records(
        request,
        rows,
        [
            "id",
            "agent_id",
            "title",
            "safety_state",
            "prompt_version",
            "model_version",
            "created_at",
        ],
    )


@endpoint(["GET", "DELETE"])
def ai_conversation(request, data, conversation_id):
    from aiteam.models import Conversation

    row = get_object_or_404(Conversation, pk=conversation_id, owner=request.user)
    if request.method == "DELETE":
        audit(request.user, "ai.conversation.deleted", row)
        row.delete()
        return {"data": {"id": str(conversation_id), "deleted": True}}, 200
    return {
        "data": {
            "id": str(row.pk),
            "agent_id": row.agent_id,
            "title": row.title,
            "safety_state": row.safety_state,
            "messages": [
                {
                    "id": str(message.pk),
                    "role": message.role,
                    "content": message.content,
                    "actions": message.actions,
                    "created_at": message.created_at,
                }
                for message in row.messages.order_by("created_at", "pk")
            ],
        }
    }, 200


@endpoint(["GET"])
def entitlements(request, data):
    """What this account may do right now, and where the numbers come from."""
    from billing.services import CAPABILITIES, allowance, current_plan, unlimited

    plan = current_plan(request.user)
    return {
        "data": {
            "plan": plan.code if plan else None,
            "plan_name": plan.name if plan else None,
            "enforced": not unlimited(),
            "capabilities": {
                key: {"description": text, "limit": allowance(request.user, key)}
                for key, text in CAPABILITIES.items()
            },
        }
    }, 200


@endpoint(["GET"])
def subscriptions(request, data):
    from billing.models import Subscription

    row = Subscription.objects.filter(user=request.user).select_related("plan").first()
    if row is None:
        return {"data": None}, 200
    return {
        "data": {
            "plan": row.plan_id,
            "state": row.state,
            "access_until": row.access_until,
            "cancel_at_period_end": row.cancel_at_period_end,
            "verified_at": row.verified_at,
            "provider": row.provider,
        }
    }, 200


@endpoint(["GET", "POST"])
def reports(request, data):
    """Trust and safety reports this account has made."""
    from network.models import Report

    if request.method == "POST":
        reason = str(data.get("reason", "")).strip()
        if len(reason) < 10:
            raise ValidationError("Describe the problem in at least 10 characters.")
        target = data.get("user")
        opportunity = data.get("opportunity")
        if not target and not opportunity:
            raise ValidationError("Name the account or opportunity being reported.")
        row = Report.objects.create(
            reporter=request.user,
            target_user=get_object_or_404(User, pk=target) if target else None,
            opportunity_id=opportunity or None,
            reason=reason[:4000],
        )
        audit(request.user, "report.submitted", row)
        return {"data": {"id": row.pk, "state": row.state}}, 201
    return records(
        request,
        Report.objects.filter(reporter=request.user).order_by("-created_at"),
        ["id", "target_user_id", "opportunity_id", "reason", "state", "created_at"],
    )
