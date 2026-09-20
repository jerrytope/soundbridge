"""Creator directory, connections, collaborations and opportunities.

Replaces the `connections`, `projects`, `applications` and `drafts` arrays in
the workspace blob. States follow PRD 8.3; the extra state that the current
screens do not yet expose is modelled now so the later phase does not need a
migration of live data.
"""

import uuid

from django.conf import settings
from django.db import models


class Creator(models.Model):
    """Sample creator directory, seeded from src/creators.js.

    These are illustrative profiles, not real accounts, exactly as the current
    Discover screen states on the page.
    """

    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=300)
    initials = models.CharField(max_length=8)
    role = models.CharField(max_length=120)
    city = models.CharField(max_length=120)
    country = models.CharField(max_length=120)
    bio = models.TextField()
    genres = models.JSONField(default=list)
    match_score = models.IntegerField(default=0)

    class Meta:
        ordering = ["external_id"]

    def __str__(self):
        return self.name


class Connection(models.Model):
    """PRD 8.3 connection request states."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    STATES = [
        (PENDING, "Pending"),
        (ACCEPTED, "Accepted"),
        (DECLINED, "Declined"),
        (CANCELLED, "Cancelled"),
        (BLOCKED, "Blocked"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="connections"
    )
    creator = models.ForeignKey(
        Creator, on_delete=models.CASCADE, related_name="connections"
    )
    # Saving a sample creator is an accepted connection in the current UI;
    # request states apply once real accounts can be connected.
    state = models.CharField(max_length=20, choices=STATES, default=ACCEPTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "creator"], name="unique_user_creator"
            )
        ]
        ordering = ["created_at"]


class Collaboration(models.Model):
    """PRD 8.3 collaboration brief."""

    DRAFT = "draft"
    OPEN = "open"
    MATCHED = "matched"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STATES = [
        (DRAFT, "Draft"),
        (OPEN, "Open"),
        (MATCHED, "Matched"),
        (ACTIVE, "Active"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collaborations",
    )
    title = models.CharField(max_length=300)
    brief = models.TextField(max_length=4000)
    collaborator = models.CharField(max_length=300, default="Not assigned")
    role_needed = models.CharField(max_length=120, blank=True)
    genre = models.CharField(max_length=120, blank=True)
    budget_visible = models.BooleanField(default=False)
    budget_amount = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    budget_currency = models.CharField(
        max_length=3,
        choices=[("USD", "USD"), ("NGN", "NGN"), ("EUR", "EUR"), ("GBP", "GBP")],
        blank=True,
    )
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    state = models.CharField(max_length=20, choices=STATES, default=DRAFT)
    # The current UI tracks a single completion flag; state carries the detail.
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title


class Participant(models.Model):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    STATES = [
        (PENDING, "Pending"),
        (ACCEPTED, "Accepted"),
        (DECLINED, "Declined"),
        (EXPIRED, "Expired"),
    ]

    collaboration = models.ForeignKey(
        Collaboration, on_delete=models.CASCADE, related_name="participants"
    )
    creator = models.ForeignKey(
        Creator, on_delete=models.SET_NULL, null=True, blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collaboration_invitations",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    display_name = models.CharField(max_length=300)
    role = models.CharField(max_length=120, blank=True)
    invitation_state = models.CharField(max_length=20, choices=STATES, default=PENDING)
    invited_at = models.DateTimeField(auto_now_add=True)


class Milestone(models.Model):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    STATES = [
        (NOT_STARTED, "Not started"),
        (IN_PROGRESS, "In progress"),
        (BLOCKED, "Blocked"),
        (COMPLETED, "Completed"),
    ]

    collaboration = models.ForeignKey(
        Collaboration, on_delete=models.CASCADE, related_name="milestones"
    )
    participant = models.ForeignKey(
        Participant, on_delete=models.SET_NULL, null=True, blank=True
    )
    title = models.CharField(max_length=300)
    assignee = models.CharField(max_length=300, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    state = models.CharField(max_length=20, choices=STATES, default=NOT_STARTED)
    created_at = models.DateTimeField(auto_now_add=True)


class SplitProposal(models.Model):
    """Ownership split capture. Acknowledgement is not a legal signature (PRD 8.3)."""

    DRAFT = "draft"
    PROPOSED = "proposed"
    ACKNOWLEDGED = "acknowledged"
    DISPUTED = "disputed"
    STATES = [
        (DRAFT, "Draft"),
        (PROPOSED, "Proposed"),
        (ACKNOWLEDGED, "Acknowledged"),
        (DISPUTED, "Disputed"),
    ]

    collaboration = models.ForeignKey(
        Collaboration, on_delete=models.CASCADE, related_name="splits"
    )
    party = models.CharField(max_length=300)
    role = models.CharField(max_length=120, blank=True)
    share_percent = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    state = models.CharField(max_length=20, choices=STATES, default=DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)


class Opportunity(models.Model):
    """Sample opportunity directory, seeded from the list in src/main.jsx.

    Verification state is explicit so a label always has a documented meaning
    (PRD 14.1); these seeded rows are unverified samples.
    """

    UNVERIFIED = "unverified"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    STATES = [
        (UNVERIFIED, "Unverified sample"),
        (UNDER_REVIEW, "Under review"),
        (VERIFIED, "Verified"),
        (REJECTED, "Rejected"),
    ]

    slug = models.SlugField(max_length=60, unique=True)
    title = models.CharField(max_length=300)
    type = models.CharField(max_length=60)
    city = models.CharField(max_length=120)
    description = models.TextField()
    source = models.CharField(max_length=300, blank=True)
    eligibility = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    cost = models.CharField(max_length=120, blank=True)
    url = models.URLField(blank=True)
    verification_state = models.CharField(
        max_length=20, choices=STATES, default=UNVERIFIED
    )
    verification_evidence = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    is_sample = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.title


class OpportunityApplication(models.Model):
    """A workspace draft. Nothing is submitted anywhere (PRD 5.3)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications"
    )
    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.CASCADE, related_name="applications"
    )
    pitch = models.TextField(max_length=8000)
    status = models.CharField(
        max_length=20,
        default="draft",
        choices=[
            ("draft", "Draft"),
            ("applied", "Marked applied by you"),
            ("withdrawn", "Withdrawn"),
        ],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "opportunity"], name="unique_user_opportunity"
            )
        ]


class OutreachDraft(models.Model):
    """Earlier planning templates kept in the AI work library."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="drafts"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class CreatorConnection(models.Model):
    """Real account relationships; legacy Connection remains a sample bookmark."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Either side may become NULL when that account is deleted under a policy
    # that keeps shared history. The remaining participant can still read the
    # thread; nobody can act on a connection that has lost a party.
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_connections",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_connections",
    )
    pair_key = models.CharField(max_length=73, unique=True)
    state = models.CharField(
        max_length=20, default="pending", choices=Connection.STATES
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(requester=models.F("recipient")),
                name="connection_not_self",
            )
        ]


class UserBlock(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks"
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "target"], name="unique_user_block"
            )
        ]


class Report(models.Model):
    collaboration_message = models.ForeignKey(
        "CollaborationMessage", on_delete=models.SET_NULL, null=True, blank=True
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_received",
    )
    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.SET_NULL, null=True, blank=True
    )
    reason = models.TextField(max_length=4000)
    state = models.CharField(
        max_length=20,
        default="open",
        choices=[
            ("open", "Open"),
            ("reviewing", "Reviewing"),
            ("resolved", "Resolved"),
        ],
    )
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DirectMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        CreatorConnection, on_delete=models.CASCADE, related_name="messages"
    )
    # A message lives in someone else's thread too, so deleting the sender's
    # account does not have to erase the other person's history: the approved
    # retention policy decides between removal and anonymised retention.
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    body = models.TextField(max_length=8000)
    client_id = models.UUIDField()
    redacted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sender", "client_id"], name="message_retry_key"
            )
        ]
        ordering = ["created_at", "id"]


class ThreadPreference(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    connection = models.ForeignKey(CreatorConnection, on_delete=models.CASCADE)
    muted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "connection"], name="thread_preference"
            )
        ]


class SavedOpportunity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "opportunity"], name="saved_opportunity"
            )
        ]


class CollaborationMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaboration = models.ForeignKey(
        Collaboration, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    body = models.TextField(max_length=8000)
    client_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sender", "client_id"], name="collaboration_message_retry"
            )
        ]
        ordering = ["created_at", "id"]


class CollaborationFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaboration = models.ForeignKey(
        Collaboration, on_delete=models.CASCADE, related_name="files"
    )
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    name = models.CharField(max_length=200)
    content = models.BinaryField()
    state = models.CharField(max_length=20, default="quarantined")
    created_at = models.DateTimeField(auto_now_add=True)


class SplitRound(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaboration = models.ForeignKey(
        Collaboration, on_delete=models.CASCADE, related_name="split_rounds"
    )
    version = models.PositiveIntegerField()
    shares = models.JSONField()
    state = models.CharField(
        max_length=20, default="proposed", choices=SplitProposal.STATES
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["collaboration", "version"], name="split_round_version"
            )
        ]


class SplitResponse(models.Model):
    proposal = models.ForeignKey(
        SplitRound, on_delete=models.CASCADE, related_name="responses"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    response = models.CharField(
        max_length=20,
        choices=[("acknowledged", "Acknowledged"), ("disputed", "Disputed")],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "user"], name="split_response_user"
            )
        ]


class CollaborationPreference(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    collaboration = models.ForeignKey(Collaboration, on_delete=models.CASCADE)
    muted = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "collaboration"], name="collaboration_preference"
        )]
