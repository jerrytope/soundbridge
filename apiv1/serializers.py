"""Translate between the relational models and the workspace JSON contract.

The React app, the existing tests and any saved export all expect the shape
defined by `emptyState` in src/domain.js. That shape is preserved exactly here;
underneath, the data lives in proper tables with decimal-safe money.
"""

import uuid
from decimal import Decimal

from django.db import transaction

from aiteam.models import ArtistBrief, Conversation, Deliverable, Message
from network.models import (
    Collaboration,
    Connection,
    Creator,
    Opportunity,
    OpportunityApplication,
    OutreachDraft,
)
from releases.models import ReleaseProject, ReleaseTask
from royalties.models import (
    CURRENCIES,
    Calculation,
    IncomeSource,
    RoyaltyTransaction,
    Statement,
)

CURRENCY_CODES = [code for code, _ in CURRENCIES]
ARRAY_KEYS = [
    "connections",
    "projects",
    "applications",
    "releases",
    "statements",
    "calculations",
    "drafts",
    "aiConversations",
    "aiDeliverables",
    "royaltySources",
]


class WorkspaceError(ValueError):
    """Raised with the same message the Node validator produced."""


def empty_state():
    return {
        "profile": {
            "name": "",
            "photo": "",
            "email": "",
            "role": "Artist",
            "city": "",
            "bio": "",
            "genres": [],
            "goals": [],
        },
        **{key: [] for key in ARRAY_KEYS},
    }


def _number(value):
    """Preserve exact money values when exporting the legacy read model."""
    return str(value) if isinstance(value, Decimal) else value


def workspace_for(user):
    """Build the workspace JSON for this account."""
    profile = user.profile
    state = empty_state()
    state["profile"].update(
        {
            "name": profile.name,
            "photo": profile.photo,
            "email": user.email,
            "role": profile.role,
            "city": profile.city,
            "bio": profile.bio,
            "portfolio": profile.portfolio,
            "genres": list(profile.genres),
            "goals": list(profile.goals),
        }
    )
    state["connections"] = list(
        Connection.objects.filter(user=user).values_list(
            "creator__external_id", flat=True
        )
    )
    state["projects"] = [
        {
            "id": str(project.id),
            "title": project.title,
            "brief": project.brief,
            "creator": project.collaborator,
            "done": project.done,
        }
        for project in Collaboration.objects.filter(owner=user)
    ]
    state["applications"] = [
        {
            "id": application.opportunity.slug,
            "title": application.opportunity.title,
            "pitch": application.pitch,
        }
        for application in OpportunityApplication.objects.filter(
            user=user
        ).select_related("opportunity")
    ]
    state["releases"] = [
        {
            "id": str(release.id),
            "title": release.title,
            "type": release.type,
            "date": release.date.isoformat(),
            "artwork": release.artwork,
            "tasks": [
                {"id": str(task.id), "title": task.title, "done": task.done}
                for task in release.tasks.all()
            ],
        }
        for release in ReleaseProject.objects.filter(owner=user).prefetch_related(
            "tasks"
        )
    ]
    state["statements"] = [
        {
            "id": str(statement.id),
            "name": statement.name,
            "rows": [
                {
                    "track": row.track,
                    "platform": row.platform,
                    "amount": _number(row.amount),
                    "currency": row.currency,
                }
                for row in statement.transactions.all()
            ],
        }
        for statement in Statement.objects.filter(owner=user).prefetch_related(
            "transactions"
        )
    ]
    state["calculations"] = [
        {
            "id": str(calculation.id),
            "platform": calculation.platform,
            "streams": calculation.streams,
            "rate": _number(calculation.rate),
            "share": _number(calculation.share),
            "currency": calculation.currency,
            "amount": _number(calculation.amount),
        }
        for calculation in Calculation.objects.filter(owner=user)
    ]
    state["drafts"] = [
        {"id": str(draft.id), "text": draft.text}
        for draft in OutreachDraft.objects.filter(user=user)
    ]
    state["aiConversations"] = [
        {
            "id": str(conversation.id),
            "agentId": conversation.agent_id,
            "title": conversation.title,
            "createdAt": conversation.created_at.isoformat(),
            "context": conversation.context,
            "workflow": conversation.workflow,
            "handoff": conversation.handoff,
            "draft": conversation.draft,
            "messages": [
                {
                    "id": str(message.id),
                    "role": message.role,
                    "content": message.content,
                    "actions": message.actions,
                    "createdAt": message.created_at.isoformat(),
                }
                for message in conversation.messages.all()
            ],
        }
        for conversation in Conversation.objects.filter(owner=user).prefetch_related(
            "messages"
        )
    ]
    state["aiDeliverables"] = [
        {
            "id": str(item.id),
            "messageId": str(item.message_id),
            "agentId": item.agent_id,
            "sessionId": str(item.conversation_id),
            "title": item.title,
            "content": item.content,
            "actions": item.actions,
            "createdAt": item.created_at.isoformat(),
        }
        for item in Deliverable.objects.filter(owner=user)
    ]
    state["royaltySources"] = list(
        IncomeSource.objects.filter(user=user).values_list("name", flat=True)
    )
    brief = ArtistBrief.objects.filter(user=user).first()
    if brief:
        state["aiBrief"] = brief.as_dict()
    return state


def validate_workspace(value, email, owns_image):
    """Port of validateWorkspace() in server/backend.js, error strings included."""
    if not isinstance(value, dict) or not isinstance(value.get("profile"), dict):
        raise WorkspaceError("Invalid workspace.")
    result = empty_state()
    for key in ARRAY_KEYS:
        items = value.get(key)
        if not isinstance(items, list) or len(items) > 1000:
            raise WorkspaceError(f"Invalid {key}.")
        result[key] = items
    profile = value["profile"]
    for key in ("name", "role", "city", "bio", "portfolio", "photo"):
        text = profile.get(key, "") or ""
        if not isinstance(text, str) or len(text) > (1000 if key == "bio" else 300):
            raise WorkspaceError(f"Invalid profile {key}.")
        result["profile"][key] = text
    if not result["profile"]["name"].strip():
        raise WorkspaceError("Enter your name.")
    portfolio = result["profile"]["portfolio"]
    if portfolio and not portfolio.lower().startswith(("http://", "https://")):
        raise WorkspaceError("Portfolio must be an HTTP or HTTPS URL.")
    for key in ("genres", "goals"):
        items = profile.get(key)
        if (
            not isinstance(items, list)
            or len(items) > 20
            or any(not isinstance(item, str) or len(item) > 100 for item in items)
        ):
            raise WorkspaceError(f"Invalid {key}.")
        result["profile"][key] = items
    result["profile"]["email"] = email
    photo = result["profile"]["photo"]
    if photo and not owns_image(photo):
        raise WorkspaceError("Image does not belong to this account.")
    for release in result["releases"]:
        _validate_release(release, owns_image)
    for key in (
        "projects",
        "applications",
        "statements",
        "calculations",
        "drafts",
        "aiConversations",
        "aiDeliverables",
    ):
        if any(not isinstance(item, dict) for item in result[key]):
            raise WorkspaceError(f"Invalid {key}.")
    for statement in result["statements"]:
        rows = statement.get("rows")
        if not isinstance(rows, list) or any(
            not isinstance(row, dict)
            or not isinstance(row.get("amount"), (int, float))
            or isinstance(row.get("amount"), bool)
            or row.get("currency") not in CURRENCY_CODES
            for row in rows
        ):
            raise WorkspaceError("Invalid statement.")
    for conversation in result["aiConversations"]:
        if not isinstance(conversation.get("messages"), list):
            raise WorkspaceError("Invalid conversation.")
    if value.get("aiBrief") is not None:
        if not isinstance(value["aiBrief"], dict):
            raise WorkspaceError("Invalid brief.")
        result["aiBrief"] = value["aiBrief"]
    return result


def _validate_release(release, owns_image):
    if (
        not isinstance(release, dict)
        or not isinstance(release.get("id"), str)
        or not isinstance(release.get("title"), str)
        or not release["title"].strip()
        or len(release["title"]) > 300
        or release.get("type") not in ("Single", "EP", "Album")
        or not isinstance(release.get("date"), str)
        or not _is_date(release["date"])
        or not isinstance(release.get("tasks"), list)
        or len(release["tasks"]) > 1000
        or any(
            not isinstance(task, dict)
            or not isinstance(task.get("id"), str)
            or not isinstance(task.get("title"), str)
            or len(task["title"]) > 2000
            or not isinstance(task.get("done"), bool)
            for task in release["tasks"]
        )
    ):
        raise WorkspaceError("Invalid release plan.")
    artwork = release.get("artwork") or ""
    if artwork and not owns_image(artwork):
        raise WorkspaceError("Image does not belong to this account.")


def _is_date(value):
    parts = value.split("-")
    return (
        len(parts) == 3
        and len(parts[0]) == 4
        and len(parts[1]) == 2
        and len(parts[2]) == 2
        and all(part.isdigit() for part in parts)
    )


@transaction.atomic
def apply_workspace(user, state):
    """Write a validated workspace back onto the relational models."""
    profile = user.profile
    incoming = state["profile"]
    profile.name = incoming["name"]
    profile.photo = incoming["photo"]
    profile.role = incoming["role"]
    profile.city = incoming["city"]
    profile.bio = incoming["bio"]
    profile.portfolio = incoming.get("portfolio", "")
    profile.genres = incoming["genres"]
    profile.goals = incoming["goals"]
    profile.save()

    _replace_connections(user, state["connections"])
    _replace_collaborations(user, state["projects"])
    _replace_applications(user, state["applications"])
    _replace_releases(user, state["releases"])
    _replace_statements(user, state["statements"])
    _replace_calculations(user, state["calculations"])
    _replace_drafts(user, state["drafts"])
    _replace_sources(user, state["royaltySources"])
    _replace_conversations(user, state["aiConversations"], state["aiDeliverables"])
    if "aiBrief" in state:
        brief, _ = ArtistBrief.objects.get_or_create(user=user)
        incoming_brief = state["aiBrief"]
        brief.project = str(incoming_brief.get("project", ""))[:300]
        brief.objective = str(incoming_brief.get("objective", ""))[:2000]
        brief.audience = str(incoming_brief.get("audience", ""))[:300]
        brief.budget = str(incoming_brief.get("budget", ""))[:300]
        brief.timeline = str(incoming_brief.get("timeline", ""))[:300]
        brief.save()


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return uuid.uuid4()


def _replace_connections(user, external_ids):
    Connection.objects.filter(user=user).delete()
    creators = {creator.external_id: creator for creator in Creator.objects.all()}
    Connection.objects.bulk_create(
        [
            Connection(user=user, creator=creators[external_id])
            for external_id in dict.fromkeys(external_ids)
            if external_id in creators
        ]
    )


def _replace_collaborations(user, projects):
    Collaboration.objects.filter(owner=user).delete()
    Collaboration.objects.bulk_create(
        [
            Collaboration(
                id=_uuid(project.get("id")),
                owner=user,
                title=str(project.get("title", ""))[:300],
                brief=str(project.get("brief", ""))[:4000],
                collaborator=str(project.get("creator", "Not assigned"))[:300],
                done=bool(project.get("done")),
                state=Collaboration.COMPLETED
                if project.get("done")
                else Collaboration.DRAFT,
            )
            for project in projects
        ]
    )


def _replace_applications(user, applications):
    OpportunityApplication.objects.filter(user=user).delete()
    opportunities = {item.slug: item for item in Opportunity.objects.all()}
    OpportunityApplication.objects.bulk_create(
        [
            OpportunityApplication(
                user=user,
                opportunity=opportunities[application["id"]],
                pitch=str(application.get("pitch", ""))[:8000],
            )
            for application in applications
            if application.get("id") in opportunities
        ]
    )


def _replace_releases(user, releases):
    ReleaseProject.objects.filter(owner=user).delete()
    for release in releases:
        project = ReleaseProject.objects.create(
            id=_uuid(release["id"]),
            owner=user,
            title=release["title"][:300],
            type=release["type"],
            date=release["date"],
            artwork=release.get("artwork", ""),
        )
        ReleaseTask.objects.bulk_create(
            [
                ReleaseTask(
                    id=_uuid(task["id"]),
                    release=project,
                    title=task["title"][:2000],
                    done=task["done"],
                    position=index,
                )
                for index, task in enumerate(release["tasks"])
            ]
        )


def _replace_statements(user, statements):
    Statement.objects.filter(owner=user).delete()
    for statement in statements:
        record = Statement.objects.create(
            id=_uuid(statement.get("id")),
            owner=user,
            name=str(statement.get("name", ""))[:300],
        )
        RoyaltyTransaction.objects.bulk_create(
            [
                RoyaltyTransaction(
                    statement=record,
                    position=index,
                    track=str(row.get("track", ""))[:500],
                    platform=str(row.get("platform", ""))[:300],
                    amount=Decimal(str(row["amount"])),
                    currency=row["currency"],
                )
                for index, row in enumerate(statement["rows"])
            ]
        )


def _replace_calculations(user, calculations):
    Calculation.objects.filter(owner=user).delete()
    Calculation.objects.bulk_create(
        [
            Calculation(
                id=_uuid(calculation.get("id")),
                owner=user,
                platform=str(calculation.get("platform", ""))[:300],
                streams=int(calculation.get("streams", 0)),
                rate=Decimal(str(calculation.get("rate", 0))),
                share=Decimal(str(calculation.get("share", 0))),
                currency=calculation.get("currency", "USD"),
                amount=Decimal(str(calculation.get("amount", 0))),
            )
            for calculation in calculations
        ]
    )


def _replace_drafts(user, drafts):
    OutreachDraft.objects.filter(user=user).delete()
    OutreachDraft.objects.bulk_create(
        [
            OutreachDraft(
                id=_uuid(draft.get("id")), user=user, text=str(draft.get("text", ""))
            )
            for draft in drafts
        ]
    )


def _replace_sources(user, sources):
    IncomeSource.objects.filter(user=user).delete()
    IncomeSource.objects.bulk_create(
        [
            IncomeSource(user=user, name=str(name)[:120])
            for name in dict.fromkeys(sources)
        ]
    )


def _replace_conversations(user, conversations, deliverables):
    Conversation.objects.filter(owner=user).delete()
    for conversation in conversations:
        record = Conversation.objects.create(
            id=_uuid(conversation.get("id")),
            owner=user,
            agent_id=str(conversation.get("agentId", ""))[:40],
            title=str(conversation.get("title", ""))[:300],
            context=conversation.get("context") or {},
            workflow=conversation.get("workflow"),
            handoff=conversation.get("handoff"),
            draft=str(conversation.get("draft", "")),
        )
        Message.objects.bulk_create(
            [
                Message(
                    id=_uuid(message.get("id")),
                    conversation=record,
                    role=message.get("role", "user"),
                    content=str(message.get("content", ""))[:16000],
                    actions=message.get("actions") or [],
                )
                for message in conversation.get("messages", [])
            ]
        )
    known_messages = {
        str(message.id): message
        for message in Message.objects.filter(conversation__owner=user)
    }
    known_conversations = {
        str(item.id): item for item in Conversation.objects.filter(owner=user)
    }
    Deliverable.objects.bulk_create(
        [
            Deliverable(
                id=_uuid(item.get("id")),
                owner=user,
                conversation=known_conversations[str(item.get("sessionId"))],
                message=known_messages[str(item.get("messageId"))],
                agent_id=str(item.get("agentId", ""))[:40],
                title=str(item.get("title", ""))[:300],
                content=str(item.get("content", "")),
                actions=item.get("actions") or [],
            )
            for item in deliverables
            if str(item.get("sessionId")) in known_conversations
            and str(item.get("messageId")) in known_messages
        ]
    )
