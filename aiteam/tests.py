from django.test import TestCase, override_settings
from accounts.models import Consent
from aiteam.models import ContextPreference, Conversation, Message, DailyUsage
from aiteam.agents import artist_context, agents
from aiteam.views import _consume_allowance
from apiv1.tests import make_user


class GovernanceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_no_context_without_explicit_permission(self):
        self.assertEqual(artist_context(self.user), {})
        ContextPreference.objects.create(user=self.user, profile=True)
        self.assertEqual(artist_context(self.user), {})
        Consent.objects.create(
            user=self.user, purpose="ai-context", version="1", granted=True
        )
        context = artist_context(self.user)
        self.assertEqual(set(context), {"artist"})
        self.assertNotIn("email", context["artist"])
        self.client.post(
            "/settings/privacy",
            {"password": "correcthorsebattery1", "action": "revoke-ai"},
        )
        self.assertEqual(artist_context(self.user), {})

    def test_delete_and_feedback_are_owner_scoped(self):
        row = Conversation.objects.create(
            owner=self.user, agent_id="manager", title="Private"
        )
        message = Message.objects.create(
            conversation=row, role="assistant", content="Advice"
        )
        self.client.post(
            f"/assistants/feedback/{message.pk}",
            {"rating": "harmful", "details": "Unsupported claim"},
        )
        row.refresh_from_db()
        self.assertEqual(row.safety_state, "flagged")
        self.client.force_login(make_user("other@example.com"))
        self.assertEqual(
            self.client.post(f"/assistants/delete/{row.pk}").status_code, 404
        )
        self.client.force_login(self.user)
        self.client.post(f"/assistants/delete/{row.pk}")
        self.assertFalse(Message.objects.filter(pk=message.pk).exists())

    @override_settings(AI_DAILY_LIMIT=1)
    def test_atomic_allowance_caps_sequential_retries(self):
        self.assertEqual(_consume_allowance(self.user), "")
        self.assertTrue(_consume_allowance(self.user))
        self.assertEqual(DailyUsage.objects.get().count, 1)

    def test_prd_roles_are_available_and_historical_ids_preserved(self):
        ids = {agent["id"] for agent in agents()}
        self.assertTrue(
            {
                "manager",
                "ar",
                "legal",
                "marketing",
                "royalties",
                "strategy",
                "matcher",
                "profile_manager",
                "release_planner",
            }
            <= ids
        )
        self.assertTrue({"producer", "songwriter", "publicist", "live"} <= ids)
