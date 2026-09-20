"""The resource groups added to complete PRD section 19.2 coverage.

Each group is checked for the three things the contract promises: it needs a
session, it answers in the documented envelope, and it refuses to leak or
accept another account's data.
"""

import json
import uuid

from django.test import TestCase
from django.utils import timezone

from apiv1.tests import make_user
from billing.tests import approve_plan
from network.models import Collaboration, Opportunity, Report


class ResourceTestCase(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def get(self, path):
        return self.client.get(path)

    def send(self, path, payload, method="post"):
        return getattr(self.client, method)(
            path,
            json.dumps(payload),
            content_type="application/json",
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )


class GoalsAndCreditsTests(ResourceTestCase):
    def test_goals_are_listed_and_replaced(self):
        response = self.send("/api/v1/goals", {"goals": ["Plan a release"]}, "put")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["goals"], ["Plan a release"])
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.goals, ["Plan a release"])

    def test_more_than_three_goals_is_refused(self):
        response = self.send(
            "/api/v1/goals",
            {
                "goals": [
                    "Plan a release",
                    "Find collaborators",
                    "Understand royalties",
                    "Grow my audience",
                ]
            },
            "put",
        )
        self.assertEqual(response.status_code, 400)

    def test_an_unknown_goal_is_refused(self):
        response = self.send("/api/v1/goals", {"goals": ["Become famous"]}, "put")
        self.assertEqual(response.status_code, 400)

    def test_a_credit_is_created_as_self_reported(self):
        response = self.send(
            "/api/v1/credits",
            {"work": "Night Drive", "role": "Producer", "source": "https://example.com/credit"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["verification_state"], "pending")
        listing = self.get("/api/v1/credits").json()
        self.assertEqual(listing["data"][0]["work"], "Night Drive")
        self.assertEqual(listing["pagination"]["count"], 1)

    def test_credits_of_another_account_are_not_listed(self):
        other = make_user("other@example.com")
        other.profile.credits.create(
            work="Theirs", role="Engineer", source="https://example.com/x"
        )
        self.assertEqual(self.get("/api/v1/credits").json()["pagination"]["count"], 0)


class CollaborationResourceTests(ResourceTestCase):
    def test_create_and_list(self):
        response = self.send(
            "/api/v1/collaborations", {"title": "First EP", "brief": "Two tracks"}
        )
        self.assertEqual(response.status_code, 201)
        listing = self.get("/api/v1/collaborations").json()
        self.assertEqual(listing["data"][0]["title"], "First EP")

    def test_a_brief_is_required(self):
        self.assertEqual(
            self.send("/api/v1/collaborations", {"title": "No brief"}).status_code, 400
        )

    def test_the_plan_limit_answers_402(self):
        approve_plan(active_collaborations=0)
        response = self.send(
            "/api/v1/collaborations", {"title": "Blocked", "brief": "Nope"}
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["error"]["code"], "entitlement")

    def test_another_accounts_collaboration_is_not_listed(self):
        other = make_user("other@example.com")
        Collaboration.objects.create(owner=other, title="Theirs", brief="Private")
        self.assertEqual(
            self.get("/api/v1/collaborations").json()["pagination"]["count"], 0
        )


class OpportunityResourceTests(ResourceTestCase):
    def setUp(self):
        super().setUp()
        Opportunity.objects.create(
            slug="verified-brief",
            title="Verified brief",
            type="Sync",
            city="Lagos",
            description="A checked listing",
            verification_state=Opportunity.VERIFIED,
        )
        Opportunity.objects.create(
            slug="unverified-brief",
            title="Unverified brief",
            type="Sync",
            city="Lagos",
            description="Not checked",
            verification_state=Opportunity.UNVERIFIED,
        )

    def test_only_verified_listings_are_returned(self):
        payload = self.get("/api/v1/opportunities").json()
        self.assertEqual(payload["pagination"]["count"], 1)
        self.assertEqual(payload["data"][0]["slug"], "verified-brief")

    def test_filtering_by_type(self):
        self.assertEqual(
            self.get("/api/v1/opportunities?type=Live").json()["pagination"]["count"], 0
        )


class AiConversationResourceTests(ResourceTestCase):
    def setUp(self):
        super().setUp()
        from aiteam.models import Conversation, Message

        self.conversation = Conversation.objects.create(
            owner=self.user, agent_id="manager", title="Planning"
        )
        Message.objects.create(
            conversation=self.conversation, role="user", content="Hello"
        )

    def test_listing_and_reading(self):
        listing = self.get("/api/v1/ai-conversations").json()
        self.assertEqual(listing["pagination"]["count"], 1)
        detail = self.get(f"/api/v1/ai-conversations/{self.conversation.pk}").json()
        self.assertEqual(detail["data"]["messages"][0]["content"], "Hello")

    def test_deleting_one_conversation(self):
        response = self.client.delete(
            f"/api/v1/ai-conversations/{self.conversation.pk}",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.ai_conversations.count(), 0)

    def test_deleting_all_conversations(self):
        response = self.client.delete(
            "/api/v1/ai-conversations",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            content_type="application/json",
        )
        self.assertEqual(response.json()["data"]["deleted"], 1)
        self.assertEqual(self.user.ai_conversations.count(), 0)

    def test_another_accounts_conversation_is_not_readable(self):
        from aiteam.models import Conversation

        other = make_user("other@example.com")
        theirs = Conversation.objects.create(
            owner=other, agent_id="manager", title="Theirs"
        )
        self.assertEqual(
            self.get(f"/api/v1/ai-conversations/{theirs.pk}").status_code, 404
        )


class EntitlementResourceTests(ResourceTestCase):
    def test_reports_the_unenforced_state_in_development(self):
        payload = self.get("/api/v1/entitlements").json()["data"]
        self.assertFalse(payload["enforced"])
        self.assertIn("release_plans", payload["capabilities"])

    def test_reports_approved_plan_limits(self):
        approve_plan(release_plans=3)
        payload = self.get("/api/v1/entitlements").json()["data"]
        self.assertTrue(payload["enforced"])
        self.assertEqual(payload["plan"], "free")
        self.assertEqual(payload["capabilities"]["release_plans"]["limit"], 3)

    def test_subscription_is_null_without_one(self):
        self.assertIsNone(self.get("/api/v1/subscriptions/me").json()["data"])

    def test_subscription_is_described_when_present(self):
        from billing.models import Subscription

        plan = approve_plan("pro", release_plans=25)
        Subscription.objects.create(
            user=self.user,
            provider="fake",
            provider_reference="sub-x",
            plan=plan,
            state="active",
            access_until=timezone.now() + timezone.timedelta(days=30),
            verified_at=timezone.now(),
        )
        payload = self.get("/api/v1/subscriptions/me").json()["data"]
        self.assertEqual(payload["plan"], "pro")
        self.assertEqual(payload["state"], "active")


class ReportResourceTests(ResourceTestCase):
    def test_reporting_an_account(self):
        target = make_user("target@example.com")
        response = self.send(
            "/api/v1/reports",
            {"user": str(target.pk), "reason": "Impersonating another artist."},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Report.objects.get().state, "open")

    def test_a_short_reason_is_refused(self):
        target = make_user("target@example.com")
        self.assertEqual(
            self.send("/api/v1/reports", {"user": str(target.pk), "reason": "bad"}).status_code,
            400,
        )

    def test_a_report_needs_a_subject(self):
        self.assertEqual(
            self.send("/api/v1/reports", {"reason": "Something is wrong here."}).status_code,
            400,
        )

    def test_only_my_reports_are_listed(self):
        other = make_user("other@example.com")
        Report.objects.create(reporter=other, reason="Theirs, not mine.")
        self.assertEqual(self.get("/api/v1/reports").json()["pagination"]["count"], 0)


class AuthenticationTests(TestCase):
    def test_every_new_route_requires_a_session(self):
        paths = [
            "/api/v1/goals",
            "/api/v1/credits",
            "/api/v1/collaborations",
            "/api/v1/opportunities",
            "/api/v1/ai-conversations",
            "/api/v1/entitlements",
            "/api/v1/subscriptions/me",
            "/api/v1/reports",
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.json()["error"]["code"], "authentication_required"
                )
