"""Moderation and per-call metrics for the model gateway.

Two things the PRD asks for that a bare provider call does not give us:

*Moderation.* Before a message is sent to the model, and before a reply is
shown, it passes a moderation check. The check is a provider call, so it is
configured rather than invented: `SOUNDBRIDGE_MODERATION_MODEL` names the
OpenAI moderation model to use. When moderation is required but unavailable the
request fails closed, because "the scanner was down" is not a safe reason to
send content on.

*Metrics.* Every call records how long it took, which model and prompt version
answered, and the token counts the provider reported, so cost and latency can be
watched and a regression can be traced to a prompt or model change. No message
text is recorded here.
"""

import time

import requests
from django.conf import settings

MODERATION_ENDPOINT = "https://api.openai.com/v1/moderations"


class ModerationError(Exception):
    """Raised when content is refused, or when a required check cannot run."""

    def __init__(self, message, categories=None):
        super().__init__(message)
        self.message = message
        self.categories = categories or []


def configured():
    return bool(settings.OPENAI_API_KEY and settings.MODERATION_MODEL)


def required():
    """Moderation is mandatory on a public deployment."""
    return bool(settings.PUBLIC_ORIGIN)


def check(text, session=requests):
    """Moderate one piece of text.

    Returns the list of flagged categories, which is empty when the content is
    acceptable. Raises ModerationError when the content is flagged, or when a
    required check cannot be completed.
    """
    if not text or not text.strip():
        return []
    if not configured():
        if required():
            raise ModerationError(
                "Moderation is not configured, so this message cannot be sent."
            )
        return []
    try:
        response = session.post(
            MODERATION_ENDPOINT,
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": settings.MODERATION_MODEL, "input": text[:32000]},
            timeout=settings.AI_REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        raise ModerationError(
            "The safety check could not run, so this message was not sent. Please retry."
        )
    if response.status_code != 200:
        raise ModerationError(
            "The safety check could not run, so this message was not sent. Please retry."
        )
    results = response.json().get("results") or [{}]
    first = results[0]
    if not first.get("flagged"):
        return []
    categories = sorted(
        name for name, hit in (first.get("categories") or {}).items() if hit
    )
    raise ModerationError(
        "This message was not sent because it was flagged by the safety check.",
        categories,
    )


class Call:
    """Context manager that records one model call.

    Usage keeps the gateway readable:

        with Call(user, agent_id, "chat") as call:
            payload = provider_response()
            call.record(payload)
    """

    def __init__(self, user, agent_id, purpose):
        self.user = user
        self.agent_id = agent_id
        self.purpose = purpose
        self.started = None
        self.payload = None
        self.outcome = "ok"
        self.row = None

    def __enter__(self):
        self.started = time.monotonic()
        return self

    def record(self, payload):
        self.payload = payload or {}

    def failed(self, outcome):
        self.outcome = outcome

    def __exit__(self, exc_type, exc, traceback):
        from aiteam.models import ModelCall

        duration = int((time.monotonic() - (self.started or time.monotonic())) * 1000)
        usage = (self.payload or {}).get("usage") or {}
        if exc_type is not None and self.outcome == "ok":
            self.outcome = "error"
        self.row = ModelCall.objects.create(
            user=self.user if getattr(self.user, "pk", None) else None,
            agent_id=self.agent_id or "",
            purpose=self.purpose,
            model=settings.OPENAI_MODEL or "",
            prompt_version=_prompt_version(),
            duration_ms=duration,
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            outcome=self.outcome,
        )
        return False


def _prompt_version():
    from aiteam.agents import PROMPT_VERSION

    return PROMPT_VERSION


def usage_summary(days=7):
    """Cost and latency shape over the recent period, for the operations screen."""
    from datetime import timedelta

    from django.db.models import Avg, Count, Sum
    from django.utils import timezone

    from aiteam.models import ModelCall

    since = timezone.now() - timedelta(days=days)
    rows = ModelCall.objects.filter(created_at__gte=since)
    totals = rows.aggregate(
        calls=Count("id"),
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
        average_ms=Avg("duration_ms"),
    )
    totals["failures"] = rows.exclude(outcome="ok").count()
    totals["by_model"] = list(
        rows.values("model", "prompt_version")
        .annotate(calls=Count("id"), average_ms=Avg("duration_ms"))
        .order_by("-calls")
    )
    return totals
