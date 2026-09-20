"""The AI Team studio: specialist directory, conversations and work library.

Port of src/ai/AiStudio.jsx. The screen keeps its three views (directory,
library and conversation workspace) and its markup; conversations now live in
the database instead of the workspace blob, and messages are sent to this
server, which calls the provider through aiteam.gateway.
"""

import json

from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.views import _bump
from aiteam import agents as registry
from aiteam.agents import PROMPT_VERSION, artist_context, get_agent
from aiteam.gateway import AiError, configured, get_reply
from aiteam.models import ArtistBrief, Conversation, DailyUsage, Deliverable, Message
from django.conf import settings
from releases.models import ReleaseProject, ReleaseTask


def _brief(user):
    brief, _ = ArtistBrief.objects.get_or_create(user=user)
    return brief


@login_required
def studio(request):
    agent_id = request.GET.get("agent", "")
    session_id = request.GET.get("session", "")
    view = request.GET.get("view", "")
    conversations = list(
        Conversation.objects.filter(owner=request.user).prefetch_related("messages")
    )
    current = next((item for item in conversations if str(item.id) == session_id), None)
    agent = get_agent(current.agent_id if current else agent_id)
    brief = _brief(request.user)
    context = {
        "agents": registry.agents(),
        "workflows": registry.workflows(),
        "categories": ["All specialists", "Creative", "Growth", "Business"],
        "category": request.GET.get("category", "All specialists"),
        "conversations": conversations,
        "deliverables": list(Deliverable.objects.filter(owner=request.user)),
        "drafts": list(request.user.drafts.all()),
        "brief": brief,
        "brief_open": request.GET.get("brief") == "open",
        "view": view,
        "agent": agent,
        "current": current,
        "status": "ready" if configured() else "offline",
        "current_page": "AI Team",
    }
    if agent:
        context.update(
            _workspace_context(request, agent, current, brief, conversations)
        )
    elif context["category"] != "All specialists":
        context["agents"] = [
            a for a in registry.agents() if a["category"] == context["category"]
        ]
    return render(request, "assistants.html", context)


def _workspace_context(request, agent, current, brief, conversations):
    shared = artist_context(request.user, brief.as_dict())
    saved_message_ids = set(
        Deliverable.objects.filter(owner=request.user).values_list(
            "message_id", flat=True
        )
    )
    thread = list(current.messages.all()) if current else []
    for message in thread:
        message.saved = message.id in saved_message_ids
    last_reply = next(
        (m for m in reversed(thread) if m.role == Message.ASSISTANT), None
    )
    workflow = current.workflow if current else None
    next_id = None
    if workflow:
        steps = workflow.get("steps", [])
        index = workflow.get("index", 0)
        next_id = steps[index + 1] if index + 1 < len(steps) else None
        workflow = {
            "name": workflow.get("name", ""),
            "steps": [
                {
                    "name": get_agent(step)["name"],
                    "state": "active"
                    if position == index
                    else ("done" if position < index else ""),
                    "marker": "✓" if position < index else position + 1,
                }
                for position, step in enumerate(steps)
            ],
        }
    return {
        "thread": thread,
        "shared_context": shared,
        "shared_context_json": json.dumps(shared, indent=2),
        "last_reply": last_reply,
        "workflow": workflow,
        "next_agent": get_agent(next_id) if next_id else None,
        "handoff_default": next_id or agent["next"],
        "other_agents": [a for a in registry.agents() if a["id"] != agent["id"]],
        "earlier_sessions": [
            item
            for item in conversations
            if item.agent_id == agent["id"] and (not current or item.id != current.id)
        ],
        "releases": list(ReleaseProject.objects.filter(owner=request.user)),
        "draft": current.draft if current else request.GET.get("draft", ""),
    }


@login_required
@require_POST
def start_session(request):
    """Open a new session, optionally following a guided workflow."""
    agent_id = request.POST.get("agent", "")
    agent = get_agent(agent_id)
    if not agent:
        return redirect("/assistants")
    workflow_id = request.POST.get("workflow", "")
    workflow = next(
        (item for item in registry.workflows() if item["id"] == workflow_id), None
    )
    if workflow:
        agent = get_agent(workflow["steps"][0])
    brief = _brief(request.user)
    conversation = Conversation.objects.create(
        owner=request.user,
        agent_id=agent["id"],
        title=workflow["name"] if workflow else f"New {agent['name']} session",
        context=artist_context(request.user, brief.as_dict()),
        workflow={**workflow, "index": 0} if workflow else None,
        draft=workflow["prompt"] if workflow else "",
        prompt_version=PROMPT_VERSION,
        model_version=settings.OPENAI_MODEL,
    )
    _bump(request.user)
    return redirect(f"/assistants?agent={agent['id']}&session={conversation.id}")


@login_required
@require_POST
def send_message(request):
    """Save the creator's message and request a specialist response."""
    conversation = get_object_or_404(
        Conversation, pk=request.POST.get("session"), owner=request.user
    )
    text = (request.POST.get("message") or "").strip()
    retry = request.POST.get("retry") == "1"
    if not retry:
        if not text:
            return redirect(_session_url(conversation))
        if conversation.messages.count() >= 40:
            flash.info(
                request,
                "This session has reached its limit. Start a new session or hand off to another specialist.",
            )
            return redirect(_session_url(conversation))
        Message.objects.create(
            conversation=conversation, role=Message.USER, content=text[:16000]
        )
        if conversation.messages.count() == 1:
            conversation.title = text[:70]
        conversation.draft = ""
        conversation.save(update_fields=["title", "draft"])
    if not configured():
        flash.info(
            request, "Message saved. You can request a response when AI is connected."
        )
        return redirect(_session_url(conversation))
    limit = _consume_allowance(request.user)
    if limit:
        flash.info(request, limit)
        return redirect(_session_url(conversation))
    body = {
        "agentId": conversation.agent_id,
        "context": artist_context(request.user, _brief(request.user).as_dict()),
        "handoff": conversation.handoff,
        "messages": [
            {"role": message.role, "content": message.content}
            for message in conversation.messages.all()
        ],
    }
    try:
        reply = get_reply(body, user=request.user)
    except AiError as problem:
        flash.info(request, problem.message)
        return redirect(_session_url(conversation))
    Message.objects.create(
        conversation=conversation,
        role=Message.ASSISTANT,
        content=reply["content"],
        actions=reply["actions"],
    )
    conversation.model_version = settings.OPENAI_MODEL
    conversation.prompt_version = PROMPT_VERSION
    conversation.save(update_fields=["model_version", "prompt_version"])
    _bump(request.user)
    return redirect(_session_url(conversation))


def _consume_allowance(user):
    """Port of the per-account daily AI allowance in server/backend.js."""
    from django.utils import timezone

    from django.db import transaction
    from accounts.models import User

    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        from billing.services import limit

        daily_limit = limit(user, "ai_daily")
        if daily_limit < 1:
            return "Your daily AI request limit has been reached."
        day = timezone.now().strftime("%Y-%m-%d")
        usage, _ = DailyUsage.objects.select_for_update().get_or_create(
            user=user, day=day
        )
        if usage.count >= daily_limit:
            return "Your daily AI request limit has been reached."
        usage.count += 1
        usage.save(update_fields=["count"])
    return ""


@login_required
@require_POST
def save_draft(request):
    conversation = get_object_or_404(
        Conversation, pk=request.POST.get("session"), owner=request.user
    )
    conversation.draft = (request.POST.get("draft") or "")[:6000]
    conversation.save(update_fields=["draft"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def save_deliverable(request):
    """Save a specialist response to the work library."""
    message = get_object_or_404(
        Message, pk=request.POST.get("message"), conversation__owner=request.user
    )
    conversation = message.conversation
    Deliverable.objects.get_or_create(
        owner=request.user,
        message=message,
        defaults={
            "conversation": conversation,
            "agent_id": conversation.agent_id,
            "title": conversation.title,
            "content": message.content,
            "actions": message.actions,
        },
    )
    _bump(request.user)
    flash.info(request, "Saved to your AI work library.")
    return redirect(_session_url(conversation))


@login_required
@require_POST
def handoff(request):
    """Pass the brief and the latest response to another specialist."""
    conversation = get_object_or_404(
        Conversation, pk=request.POST.get("session"), owner=request.user
    )
    target = get_agent(request.POST.get("target"))
    if not target:
        return redirect(_session_url(conversation))
    last_reply = conversation.messages.filter(role=Message.ASSISTANT).last()
    if not last_reply:
        return redirect(_session_url(conversation))
    source = get_agent(conversation.agent_id)
    workflow = conversation.workflow
    if workflow:
        workflow = {**workflow, "index": workflow.get("index", 0) + 1}
    next_session = Conversation.objects.create(
        owner=request.user,
        agent_id=target["id"],
        title=conversation.title,
        context=conversation.context,
        workflow=workflow,
        handoff={
            "from": source["id"],
            "content": last_reply.content,
            "originalBrief": conversation.title,
        },
        draft=(
            f"Build on the {source['name']}'s work from your perspective as {target['name']}. "
            "Keep the artist's original objective and constraints in view."
        ),
        prompt_version=PROMPT_VERSION,
        model_version=settings.OPENAI_MODEL,
    )
    _bump(request.user)
    flash.info(request, f"Brief and specialist response passed to {target['name']}.")
    return redirect(_session_url(next_session))


@login_required
@require_POST
def refresh_context(request):
    conversation = get_object_or_404(
        Conversation, pk=request.POST.get("session"), owner=request.user
    )
    conversation.context = artist_context(request.user, _brief(request.user).as_dict())
    conversation.save(update_fields=["context"])
    _bump(request.user)
    flash.info(request, "Session updated with your latest artist and project brief.")
    return redirect(_session_url(conversation))


@login_required
@require_POST
def save_brief(request):
    brief = _brief(request.user)
    brief.project = (request.POST.get("project") or "")[:300]
    brief.objective = (request.POST.get("objective") or "")[:2000]
    brief.audience = (request.POST.get("audience") or "")[:300]
    brief.budget = (request.POST.get("budget") or "")[:300]
    brief.timeline = (request.POST.get("timeline") or "")[:300]
    brief.save()
    _bump(request.user)
    flash.info(request, "Project brief saved for new sessions.")
    return redirect("/assistants")


@login_required
@require_POST
def apply_actions(request):
    """Add selected next actions to a release plan (the ActionTransfer control)."""
    message = get_object_or_404(
        Message, pk=request.POST.get("message"), conversation__owner=request.user
    )
    release = get_object_or_404(
        ReleaseProject, pk=request.POST.get("release"), owner=request.user
    )
    chosen = request.POST.getlist("action")
    if not chosen:
        flash.info(request, "Choose at least one action to add.")
        return redirect(_session_url(message.conversation))
    position = release.tasks.count()
    for index in chosen:
        try:
            title = message.actions[int(index)]
        except (ValueError, IndexError):
            continue
        ReleaseTask.objects.create(
            release=release, title=title[:2000], position=position
        )
        position += 1
    _bump(request.user)
    flash.info(request, "Selected actions added to your release plan.")
    return redirect(_session_url(message.conversation))


def _session_url(conversation):
    return f"/assistants?agent={conversation.agent_id}&session={conversation.id}"


@login_required
def download_work(request, deliverable_id):
    """Download a saved specialist response, as the library button did."""
    from django.http import HttpResponse

    item = get_object_or_404(Deliverable, pk=deliverable_id, owner=request.user)
    agent = get_agent(item.agent_id)
    name = agent["name"] if agent else item.agent_id
    actions = "\n".join(item.actions)
    body = f"{name}\n{item.title}\n\n{item.content}\n\nNext actions\n{actions}"
    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = (
        'attachment; filename="soundbridge-specialist-plan.txt"'
    )
    return response


@login_required
def status(request):
    """GET /api/ai/status, as the studio's connection indicator expects."""
    return JsonResponse({"configured": configured()})
