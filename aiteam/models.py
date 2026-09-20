"""AI specialist conversations, saved work and usage counters.

Replaces the `aiConversations`, `aiDeliverables` and `aiBrief` entries in the
workspace blob and the `ai_usage` table. Prompt and model versions are stored
per conversation so a response can always be traced to what produced it
(PRD 9.1).
"""

import uuid

from django.conf import settings
from django.db import models


class ArtistBrief(models.Model):
    """The shared brief every new session starts from."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_brief"
    )
    project = models.CharField(max_length=300, blank=True)
    objective = models.TextField(max_length=2000, blank=True)
    audience = models.CharField(max_length=300, blank=True)
    budget = models.CharField(max_length=300, blank=True)
    timeline = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def as_dict(self):
        return {
            "project": self.project,
            "objective": self.objective,
            "audience": self.audience,
            "budget": self.budget,
            "timeline": self.timeline,
        }


class Conversation(models.Model):
    OK = "ok"
    FLAGGED = "flagged"
    STATES = [(OK, "OK"), (FLAGGED, "Flagged")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    agent_id = models.CharField(max_length=40)
    title = models.CharField(max_length=300)
    # The context snapshot sent with this session. Existing sessions keep their
    # original context until the creator refreshes it, as the studio states.
    context = models.JSONField(default=dict, blank=True)
    workflow = models.JSONField(null=True, blank=True)
    handoff = models.JSONField(null=True, blank=True)
    draft = models.TextField(blank=True)
    prompt_version = models.CharField(max_length=40, default="")
    model_version = models.CharField(max_length=80, default="")
    safety_state = models.CharField(max_length=20, choices=STATES, default=OK)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Message(models.Model):
    USER = "user"
    ASSISTANT = "assistant"
    ROLES = [(USER, "Creator"), (ASSISTANT, "Specialist")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=ROLES)
    content = models.TextField(max_length=16000)
    actions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class Deliverable(models.Model):
    """A specialist response the creator saved to their work library."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_deliverables",
    )
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="deliverables"
    )
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="deliverables"
    )
    agent_id = models.CharField(max_length=40)
    title = models.CharField(max_length=300)
    content = models.TextField()
    actions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class DailyUsage(models.Model):
    """Port of the ai_usage table: a request allowance per account per UTC day."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_usage"
    )
    day = models.CharField(max_length=10)
    count = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "day"], name="unique_user_day")
        ]


class ContextPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_context_preference",
    )
    profile = models.BooleanField(default=False)
    brief = models.BooleanField(default=False)
    releases = models.BooleanField(default=False)
    royalties = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


class Feedback(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="feedback"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.CharField(
        max_length=20,
        choices=[
            ("helpful", "Helpful"),
            ("unhelpful", "Unhelpful"),
            ("harmful", "Report harmful response"),
        ],
    )
    details = models.TextField(max_length=4000, blank=True)
    reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class ModelCall(models.Model):
    """One call to the model provider: cost and latency, never message text."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    agent_id = models.CharField(max_length=40, blank=True)
    purpose = models.CharField(max_length=40)
    model = models.CharField(max_length=80, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    outcome = models.CharField(max_length=20, default="ok")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at"])]


class EvaluationCase(models.Model):
    """A launch evaluation case: an input and what a good answer must satisfy."""

    slug = models.SlugField(max_length=60, unique=True)
    agent_id = models.CharField(max_length=40)
    prompt = models.TextField()
    must_include = models.JSONField(
        default=list, blank=True, help_text="Substrings the answer must contain."
    )
    must_not_include = models.JSONField(
        default=list, blank=True, help_text="Substrings that fail the case."
    )
    note = models.TextField(blank=True)
    active = models.BooleanField(default=True)


class EvaluationRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    model = models.CharField(max_length=80, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    passed = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]


class EvaluationResult(models.Model):
    run = models.ForeignKey(
        EvaluationRun, on_delete=models.CASCADE, related_name="results"
    )
    case = models.ForeignKey(EvaluationCase, on_delete=models.CASCADE)
    passed = models.BooleanField(default=False)
    detail = models.TextField(blank=True)
