"""Entitlement behaviour.

Limits come from approved `Plan` records. These tests pin the two rules that
matter: an unapproved environment enforces nothing commercial, and once plans
are approved every capability is checked against them rather than against a
number written into the code.
"""

import json
import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from apiv1.tests import make_user
from billing.models import BillingEvent, Plan, Subscription
from billing.services import EntitlementRequired, allowance, check, current_plan
from network.models import Collaboration
from releases.models import ReleaseProject
from royalties.models import Calculation


def approve_plan(code="free", **limits):
    return Plan.objects.create(
        code=code,
        name=code.title(),
        limits=limits,
        approved_at=timezone.now(),
        commercial_terms="Approved for testing",
    )


class AllowanceTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_development_without_approved_plans_enforces_nothing_commercial(self):
        self.assertIsNone(allowance(self.user, "release_plans"))
        check(self.user, "release_plans", 10_000, "Release plans")

    @override_settings(PUBLIC_ORIGIN="https://example.test")
    def test_a_public_deployment_without_plans_is_closed(self):
        self.assertEqual(allowance(self.user, "release_plans"), 0)
        with self.assertRaises(EntitlementRequired):
            check(self.user, "release_plans", 0, "Release plans")

    def test_approved_free_plan_limits_apply(self):
        approve_plan(release_plans=1)
        self.assertEqual(allowance(self.user, "release_plans"), 1)
        check(self.user, "release_plans", 0, "Release plans")
        with self.assertRaises(EntitlementRequired) as limited:
            check(self.user, "release_plans", 1, "Release plans")
        self.assertIn("1 release plans", limited.exception.message)

    def test_a_capability_missing_from_the_plan_is_disabled(self):
        approve_plan(release_plans=1)
        with self.assertRaises(EntitlementRequired) as limited:
            check(self.user, "statements", 0, "Imported statements")
        self.assertIn("not included", limited.exception.message)

    def test_an_unapproved_plan_is_ignored(self):
        Plan.objects.create(code="free", name="Free", limits={"release_plans": 5})
        self.assertIsNone(current_plan(self.user))

    def test_an_active_subscription_replaces_the_free_plan(self):
        approve_plan("free", release_plans=1)
        pro = approve_plan("pro", release_plans=25)
        Subscription.objects.create(
            user=self.user,
            provider="test",
            provider_reference=str(uuid.uuid4()),
            plan=pro,
            state="active",
            access_until=timezone.now() + timezone.timedelta(days=30),
            verified_at=timezone.now(),
        )
        self.assertEqual(allowance(self.user, "release_plans"), 25)

    def test_an_expired_subscription_falls_back_to_free(self):
        approve_plan("free", release_plans=1)
        pro = approve_plan("pro", release_plans=25)
        Subscription.objects.create(
            user=self.user,
            provider="test",
            provider_reference=str(uuid.uuid4()),
            plan=pro,
            state="active",
            access_until=timezone.now() - timezone.timedelta(days=1),
            verified_at=timezone.now(),
        )
        self.assertEqual(allowance(self.user, "release_plans"), 1)


class EnforcementTests(TestCase):
    """The limits have to bite in the screens, not only in the helper."""

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_release_plans_are_capped(self):
        approve_plan(release_plans=1, saved_calculations=1, statements=1)
        for index in range(2):
            self.client.post(
                "/release-planner",
                {
                    "action": "create",
                    "title": f"Release {index}",
                    "date": "2027-01-01",
                    "type": "Single",
                },
            )
        self.assertEqual(ReleaseProject.objects.filter(owner=self.user).count(), 1)

    def test_active_collaborations_are_capped(self):
        approve_plan(active_collaborations=1)
        for index in range(2):
            self.client.post(
                "/collaborations",
                {"title": f"Project {index}", "brief": "Work together", "creator": "Not assigned"},
            )
        self.assertEqual(Collaboration.objects.filter(owner=self.user).count(), 1)

    def test_completing_a_collaboration_frees_the_allowance(self):
        approve_plan(active_collaborations=1)
        self.client.post(
            "/collaborations",
            {"title": "First", "brief": "Work together", "creator": "Not assigned"},
        )
        project = Collaboration.objects.get(owner=self.user)
        project.state = Collaboration.COMPLETED
        project.save(update_fields=["state"])
        self.client.post(
            "/collaborations",
            {"title": "Second", "brief": "Work together", "creator": "Not assigned"},
        )
        self.assertEqual(Collaboration.objects.filter(owner=self.user).count(), 2)

    def test_saved_scenarios_are_capped(self):
        approve_plan(saved_calculations=0)
        response = self.client.post(
            "/royalty-calculator",
            {
                "action": "save",
                "platform": "Spotify",
                "streams": "1000",
                "low_rate": "0.002",
                "midpoint_rate": "0.003",
                "high_rate": "0.004",
                "share": "100",
                "deduction_percent": "0",
                "currency": "USD",
                "market": "NG",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "rate_source": "My distributor statement",
                "rate_effective_date": "2026-01-01",
                "rate_version": "v1",
            },
        )
        self.assertEqual(Calculation.objects.filter(owner=self.user).count(), 0)
        self.assertContains(response, "not included in your current plan")

    def test_statement_imports_are_capped(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from royalties.imports import upload

        approve_plan(statements=0)
        with self.assertRaises(ValidationError):
            upload(
                self.user,
                SimpleUploadedFile(
                    "statement.csv",
                    b"track,platform,amount,currency\nA,Spotify,1.00,USD\n",
                ),
            )

    def test_connection_requests_are_capped_per_day(self):
        from network import services

        approve_plan(connection_requests_daily=1)
        others = []
        for index in range(2):
            person = make_user(f"person{index}@example.com")
            person.email_verified_at = timezone.now()
            person.save(update_fields=["email_verified_at"])
            person.profile.published = True
            person.profile.save(update_fields=["published"])
            others.append(person)
        self.user.email_verified_at = timezone.now()
        self.user.save(update_fields=["email_verified_at"])
        services.request_connection(self.user, others[0])
        with self.assertRaises(ValidationError):
            services.request_connection(self.user, others[1])


class FakeProvider:
    """A provider stand-in used only by tests.

    Registered under the name "fake" so the lifecycle can be exercised without
    inventing a real provider integration or its commercial terms.
    """

    name = "fake"
    sent = []
    subscription = None
    signature_ok = True

    def start_checkout(self, user, plan, return_url):
        FakeProvider.sent.append((user.email, plan.code, return_url))
        return "https://provider.test/checkout/session"

    def verify_event(self, request):
        from billing.providers import ProviderError

        if not FakeProvider.signature_ok:
            raise ProviderError("Signature mismatch.")
        return json.loads(request.body)

    def fetch_subscription(self, reference):
        return FakeProvider.subscription

    def cancel(self, reference, at_period_end=True):
        event = dict(FakeProvider.subscription or {})
        event.update(
            {
                "event_id": "evt-cancel",
                "type": "subscription.cancelled",
                "reference": reference,
                "cancel_at_period_end": at_period_end,
                "state": "cancelled",
            }
        )
        return event


def use_fake_provider(test):
    from billing import providers

    providers.REGISTRY["fake"] = FakeProvider
    FakeProvider.sent = []
    FakeProvider.subscription = None
    FakeProvider.signature_ok = True
    test.addCleanup(providers.REGISTRY.pop, "fake", None)


def provider_event(email, plan_code="pro", **overrides):
    event = {
        "event_id": "evt-1",
        "type": "subscription.updated",
        "reference": "sub-1",
        "email": email,
        "plan_code": plan_code,
        "state": "active",
        "access_until": (timezone.now() + timezone.timedelta(days=30)).isoformat(),
    }
    event.update(overrides)
    return event


@override_settings(BILLING_PROVIDER="fake")
class ProviderLifecycleTests(TestCase):
    def setUp(self):
        use_fake_provider(self)
        self.user = make_user()
        approve_plan("free", release_plans=1)
        approve_plan("pro", release_plans=25)

    def _post_event(self, event):
        return self.client.post(
            "/billing/webhook", json.dumps(event), content_type="application/json"
        )

    def test_a_verified_event_grants_the_plan(self):
        self.assertEqual(self._post_event(provider_event(self.user.email)).status_code, 204)
        self.assertEqual(allowance(self.user, "release_plans"), 25)
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.state, "active")
        self.assertIsNotNone(subscription.verified_at)

    def test_a_repeated_event_is_applied_once(self):
        event = provider_event(self.user.email)
        self._post_event(event)
        self._post_event(event)
        self.assertEqual(BillingEvent.objects.count(), 1)
        self.assertEqual(Subscription.objects.count(), 1)

    def test_a_rejected_signature_changes_nothing(self):
        FakeProvider.signature_ok = False
        response = self._post_event(provider_event(self.user.email))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Subscription.objects.exists())

    def test_an_unapproved_plan_in_an_event_is_refused(self):
        response = self._post_event(provider_event(self.user.email, plan_code="enterprise"))
        self.assertEqual(response.status_code, 422)
        self.assertFalse(Subscription.objects.exists())

    def test_an_unknown_account_is_refused(self):
        response = self._post_event(provider_event("nobody@example.com"))
        self.assertEqual(response.status_code, 422)
        self.assertFalse(Subscription.objects.exists())

    def test_the_redirect_alone_never_grants_a_plan(self):
        self.client.force_login(self.user)
        response = self.client.post("/membership/checkout", {"plan": "pro"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("provider.test", response["Location"])
        self.assertFalse(Subscription.objects.exists())
        self.assertEqual(allowance(self.user, "release_plans"), 1)

    def test_cancellation_keeps_access_until_the_period_ends_and_keeps_data(self):
        self._post_event(provider_event(self.user.email))
        ReleaseProject.objects.create(
            owner=self.user, title="Kept", date="2027-01-01", type="Single"
        )
        FakeProvider.subscription = provider_event(self.user.email)
        self.client.force_login(self.user)
        self.client.post("/membership/cancel")
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.state, "cancelled")
        self.assertTrue(subscription.cancel_at_period_end)
        self.assertEqual(allowance(self.user, "release_plans"), 25)
        self.assertTrue(ReleaseProject.objects.filter(owner=self.user).exists())

    def test_expired_access_falls_back_without_deleting_anything(self):
        self._post_event(
            provider_event(
                self.user.email,
                access_until=(timezone.now() - timezone.timedelta(days=1)).isoformat(),
            )
        )
        ReleaseProject.objects.create(
            owner=self.user, title="Kept", date="2027-01-01", type="Single"
        )
        self.assertEqual(allowance(self.user, "release_plans"), 1)
        self.assertTrue(ReleaseProject.objects.filter(owner=self.user).exists())

    def test_reconciliation_corrects_drift(self):
        self._post_event(provider_event(self.user.email))
        FakeProvider.subscription = provider_event(
            self.user.email, plan_code="free", state="past_due", event_id="evt-2"
        )
        from billing.services import reconcile

        self.assertEqual(reconcile(), 1)
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.state, "past_due")
        self.assertEqual(subscription.plan_id, "free")

    def test_reconciliation_expires_a_subscription_the_provider_has_lost(self):
        self._post_event(provider_event(self.user.email))
        FakeProvider.subscription = None
        from billing.services import reconcile

        reconcile()
        self.assertEqual(Subscription.objects.get(user=self.user).state, "expired")
        self.assertEqual(allowance(self.user, "release_plans"), 1)

    def test_command_runs_reconciliation(self):
        from django.core.management import call_command

        self._post_event(provider_event(self.user.email))
        FakeProvider.subscription = provider_event(self.user.email)
        call_command("reconcile_billing", verbosity=0)


class ProviderNotConfiguredTests(TestCase):
    def setUp(self):
        self.user = make_user()
        approve_plan("pro", release_plans=25)

    def test_webhook_refuses_before_a_provider_is_selected(self):
        response = self.client.post(
            "/billing/webhook",
            json.dumps(provider_event(self.user.email)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Subscription.objects.exists())

    def test_checkout_explains_itself_instead_of_pretending(self):
        self.client.force_login(self.user)
        response = self.client.post("/membership/checkout", {"plan": "pro"}, follow=True)
        self.assertContains(response, "No payment provider is configured")
        self.assertFalse(Subscription.objects.exists())

    def test_membership_page_states_checkout_is_unavailable(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/membership"), "Checkout is unavailable")
