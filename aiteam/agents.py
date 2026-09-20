"""The nine specialists and the guided workflows.

`agents.json` was generated from src/ai/agents.js, so every name, tagline,
description, starter and expertise instruction is byte-identical to the
definitions the React studio used. Editing the JSON changes the prompts, so it
carries a version that is recorded on each conversation (PRD 9.1).
"""

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

DEFINITIONS = Path(__file__).resolve().parent / "agents.json"
PROMPT_VERSION = "agents-2"


@lru_cache(maxsize=1)
def _data():
    return json.loads(DEFINITIONS.read_text(encoding="utf-8"))


def agents():
    return _data()["agents"]


def workflows():
    return _data()["workflows"]


def get_agent(agent_id):
    return next((agent for agent in agents() if agent["id"] == agent_id), None)


def categories():
    """Category filter used by the studio directory."""
    seen = []
    for agent in agents():
        if agent["category"] not in seen:
            seen.append(agent["category"])
    return ["All specialists"] + seen


def artist_context(user, brief=None):
    """Port of artistContext() in src/ai/agents.js.

    Only deliberately selected context is sent: never the whole workspace, and
    never the account email.
    """
    from aiteam.models import ContextPreference

    preference = ContextPreference.objects.filter(user=user).first()
    consent = (
        user.consents.filter(purpose="ai-context")
        .order_by("-created_at", "-pk")
        .first()
    )
    if not preference or not consent or not consent.granted:
        return {}
    profile = user.profile
    brief = brief or {}
    releases = []
    for release in user.releases.all()[:8]:
        releases.append(
            {
                "title": release.title,
                "type": release.type,
                "date": release.date.isoformat(),
                "completedTasks": [
                    task.title for task in release.tasks.all() if task.done
                ],
            }
        )
    totals = {}
    for statement in user.statements.all():
        for row in statement.transactions.all():
            totals[row.currency] = totals.get(row.currency, Decimal(0)) + row.amount
    result = {
        "artist": {
            "name": profile.name,
            "role": profile.role,
            "city": profile.city,
            "bio": profile.bio,
            "genres": profile.genres,
            "goals": profile.goals,
        },
        "brief": {
            "project": brief.get("project", ""),
            "objective": brief.get("objective", ""),
            "audience": brief.get("audience", ""),
            "budget": brief.get("budget", ""),
            "timeline": brief.get("timeline", ""),
        },
        "releases": releases,
        "royaltySources": list(user.royalty_sources.values_list("name", flat=True)),
        "royaltyTotals": {currency: str(amount) for currency, amount in totals.items()},
    }

    allowed = []
    if preference.profile:
        allowed.append("artist")
    if preference.brief:
        allowed.append("brief")
    if preference.releases:
        allowed.append("releases")
    if preference.royalties:
        allowed.extend(["royaltySources", "royaltyTotals"])
    return {key: value for key, value in result.items() if key in allowed}
