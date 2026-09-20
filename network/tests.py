"""Screen-level tests: every route renders, and guarded routes redirect."""

from django.test import TestCase

from apiv1.tests import make_user
from network.models import Connection, Opportunity
from releases.models import ReleaseProject

WORKSPACE_PATHS = [
    "/portal",
    "/discover",
    "/collaborations",
    "/opportunities",
    "/assistants",
    "/assistants?view=library",
    "/royalties",
    "/royalty-calculator",
    "/royalty-upload",
    "/royalty-setup",
    "/release-planner",
    "/release-setup",
    "/analytics",
    "/music-search",
    "/membership",
    "/settings",
    "/onboarding",
    "/goals",
    "/genres",
    "/profile-setup",
]


class RoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from network.management.commands.seed_creators import Command

        Command().handle()

    def test_public_pages_render(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/signup").status_code, 200)
        self.assertEqual(self.client.get("/signup?mode=signin").status_code, 200)

    def test_workspace_pages_require_sign_in(self):
        for path in WORKSPACE_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/signup", response["Location"])

    def test_workspace_pages_render_when_signed_in(self):
        self.client.force_login(make_user())
        for path in WORKSPACE_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_creator_profile_renders(self):
        self.client.force_login(make_user())
        response = self.client.get("/creators/1")
        self.assertContains(response, "Kairo Ade")

    def test_unknown_page_returns_the_not_found_screen(self):
        response = self.client.get("/nowhere")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)

    def test_legacy_prototype_is_still_served(self):
        response = self.client.get("/portal.html")
        self.assertEqual(response.status_code, 200)


class DiscoverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from network.management.commands.seed_creators import Command

        Command().handle()

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        from network.test_mvp import creator

        profile = creator("real@example.com", "kairo").profile
        profile.name = "Kairo Ade"
        profile.role = "Producer"
        profile.genres = ["Afrobeats"]
        profile.save()

    def test_filters_by_role(self):
        response = self.client.get("/discover?role=Producer")
        self.assertContains(response, "Kairo Ade")
        self.assertNotContains(response, "Jordan Blake")

    def test_filters_by_genre_and_search(self):
        self.assertContains(self.client.get("/discover?genre=Afrobeats"), "Kairo Ade")
        self.assertContains(self.client.get("/discover?search=kairo"), "Kairo Ade")

    def test_no_match_shows_the_empty_state(self):
        self.assertContains(
            self.client.get("/discover?search=zzzz"), "No creators match your filters"
        )

    def test_saving_a_creator_toggles(self):
        self.client.post("/discover/save/1", {"next": "/discover"})
        self.assertEqual(Connection.objects.filter(user=self.user).count(), 1)
        self.client.post("/discover/save/1", {"next": "/discover"})
        self.assertEqual(Connection.objects.filter(user=self.user).count(), 0)

    def test_save_rejects_an_offsite_redirect(self):
        response = self.client.post(
            "/discover/save/1", {"next": "https://evil.example.com"}
        )
        self.assertEqual(response["Location"], "/discover")


class OnboardingTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_role_choice_is_saved(self):
        self.client.post("/onboarding", {"option": "Producer"})
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.role, "Producer")

    def test_goals_are_capped_at_three(self):
        for goal in [
            "Find collaborators",
            "Plan a release",
            "Understand royalties",
            "Grow my audience",
        ]:
            self.client.post("/goals", {"option": goal})
        self.user.profile.refresh_from_db()
        self.assertEqual(len(self.user.profile.goals), 3)

    def test_genre_choice_toggles(self):
        self.client.post("/genres", {"option": "Afrobeats"})
        self.client.post("/genres", {"option": "Afrobeats"})
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.genres, [])

    def test_profile_save_requires_http_portfolio(self):
        response = self.client.post(
            "/settings",
            {
                "name": "Temi",
                "role": "Artist",
                "city": "Lagos",
                "bio": "",
                "portfolio": "ftp://x",
            },
            follow=True,
        )
        self.assertContains(response, "Portfolio must be an HTTP or HTTPS URL.")


class CollaborationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_creating_and_completing_a_project(self):
        self.client.post(
            "/collaborations",
            {"title": "First EP", "brief": "Two tracks", "creator": "Kairo Ade"},
        )
        project = self.user.collaborations.get()
        self.assertFalse(project.done)
        self.client.post("/collaborations", {"action": "toggle", "id": str(project.id)})
        project.refresh_from_db()
        self.assertTrue(project.done)

    def test_opportunity_draft_is_saved(self):
        Opportunity.objects.create(
            slug="sync",
            title="Film music",
            type="Sync",
            city="Remote",
            description="x",
            verification_state="verified",
        )
        self.client.post(
            "/opportunities",
            {
                "slug": "sync",
                "type": "All",
                "pitch": "A pitch that is comfortably long enough.",
            },
        )
        self.assertEqual(self.user.applications.count(), 1)

    def test_short_pitch_is_not_saved(self):
        Opportunity.objects.create(
            slug="live",
            title="Showcase",
            type="Live",
            city="Accra",
            description="x",
            verification_state="verified",
        )
        self.client.post(
            "/opportunities", {"slug": "live", "type": "All", "pitch": "too short"}
        )
        self.assertEqual(self.user.applications.count(), 0)


class IsolationTests(TestCase):
    def test_one_account_cannot_see_another_release(self):
        owner = make_user("owner@example.com")
        intruder = make_user("intruder@example.com")
        release = ReleaseProject.objects.create(
            owner=owner, title="Private", date="2026-01-01"
        )
        self.client.force_login(intruder)
        self.assertNotContains(self.client.get("/release-planner"), "Private")
        response = self.client.post(
            "/release-planner",
            {"action": "add-task", "release": str(release.id), "task": "Sneak"},
        )
        self.assertEqual(response.status_code, 404)
