"""Release projects and their task checklists.

Replaces the `releases` array in the workspace blob, including the six-item
checklist the React screen creates with every new plan.
"""

import uuid

from django.conf import settings
from django.db import models

CHECKLIST = [
    "Finish recording and master",
    "Confirm artwork and credits",
    "Deliver to distributor",
    "Prepare announcement and content",
    "Pitch and schedule promotion",
    "Release and review results",
]

TYPES = [("Single", "Single"), ("EP", "EP"), ("Album", "Album")]


class ReleaseProject(models.Model):
    PLANNING = "planning"
    PRODUCTION = "production"
    DELIVERY = "delivery"
    PROMOTION = "promotion"
    RELEASED = "released"
    STAGES = [
        (PLANNING, "Planning"),
        (PRODUCTION, "Production"),
        (DELIVERY, "Delivery"),
        (PROMOTION, "Promotion"),
        (RELEASED, "Released"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="releases"
    )
    title = models.CharField(max_length=300)
    type = models.CharField(max_length=10, choices=TYPES, default="Single")
    date = models.DateField()
    stage = models.CharField(max_length=20, choices=STAGES, default=PLANNING)
    artwork = models.CharField(max_length=300, blank=True)
    support_needs = models.JSONField(default=list, blank=True)
    metadata_ready = models.JSONField(default=dict, blank=True)
    campaign_plan = models.TextField(max_length=8000, blank=True)
    reminders_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title

    @property
    def completion(self):
        tasks = list(self.tasks.all())
        if not tasks:
            return 0
        return round(100 * sum(1 for task in tasks if task.done) / len(tasks))


class ReleaseTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    release = models.ForeignKey(
        ReleaseProject, on_delete=models.CASCADE, related_name="tasks"
    )
    title = models.CharField(max_length=2000)
    done = models.BooleanField(default=False)
    position = models.IntegerField(default=0)
    assignee = models.CharField(max_length=300, blank=True)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.title
