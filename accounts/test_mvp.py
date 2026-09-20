from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from accounts.models import User, Consent, EmailVerification
from accounts.security import verify_token
from operations.models import EmailDelivery

PASSWORD = "correcthorsebattery1"


class IdentityTests(TestCase):
    def test_signup_signs_straight_in_without_verifying(self):
        """The shipped default: sign up, and the account is usable at once."""
        data = {"name": "Creator", "email": "creator@example.com", "password": PASSWORD}
        response = self.client.post("/signup", {**data, "consent": "on"})
        self.assertRedirects(response, "/portal", fetch_redirect_response=False)
        # Nothing was emailed, and nothing is waiting to be confirmed.
        self.assertEqual(EmailDelivery.objects.count(), 0)
        self.assertFalse(EmailVerification.objects.exists())
        self.assertIsNotNone(User.objects.get().email_verified_at)
        # The workspace is reachable rather than bouncing to /verify-email.
        self.assertNotIn(
            "/verify-email", getattr(self.client.get("/portal"), "url", "")
        )

    def test_signup_details_sign_in_again_without_verifying(self):
        data = {"name": "Creator", "email": "creator@example.com", "password": PASSWORD}
        self.client.post("/signup", {**data, "consent": "on"})
        self.client.post("/sign-out")
        response = self.client.post(
            "/signup?mode=signin", {"email": data["email"], "password": PASSWORD}
        )
        self.assertRedirects(response, "/portal", fetch_redirect_response=False)

    @override_settings(REQUIRE_EMAIL_VERIFICATION=True)
    def test_signup_requires_consent_and_queues_verification(self):
        data = {"name": "Creator", "email": "creator@example.com", "password": PASSWORD}
        self.client.post("/signup", data)
        self.assertFalse(User.objects.exists())
        response = self.client.post("/signup", {**data, "consent": "on"})
        self.assertRedirects(response, "/verify-email")
        self.assertEqual(Consent.objects.count(), 2)
        self.assertEqual(EmailDelivery.objects.count(), 1)
        self.assertRedirects(self.client.get("/portal"), "/verify-email")
        token = EmailDelivery.objects.get().body.rsplit("/", 1)[-1]
        self.client.get("/verify-email/" + token)
        self.assertIsNone(User.objects.get().email_verified_at)
        self.client.post("/verify-email/" + token)
        self.assertIsNotNone(User.objects.get().email_verified_at)
        self.assertFalse(verify_token(token))

    def test_expired_verification_is_rejected(self):
        user = User.objects.create_user("a@example.com", PASSWORD)
        import hashlib

        EmailVerification.objects.create(
            user=user,
            token_digest=hashlib.sha256(b"old").hexdigest(),
            expires_at=timezone.now(),
        )
        self.assertFalse(verify_token("old"))

    def test_reset_invalidates_existing_session_and_old_token(self):
        user = User.objects.create_user("a@example.com", PASSWORD)
        other = Client()
        other.force_login(user)
        token = default_token_generator.make_token(user)
        url = reverse(
            "password_reset_confirm",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": token,
            },
        )
        response = self.client.get(url)
        self.client.post(
            response["Location"],
            {
                "new_password1": "anotherstrongpassword1",
                "new_password2": "anotherstrongpassword1",
            },
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password("anotherstrongpassword1"))
        self.assertFalse(default_token_generator.check_token(user, token))
        self.assertIsNone(other.get("/api/auth/session").json()["user"])

    def test_browser_api_requires_csrf_and_logout_is_post_only(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/api/auth/login", "{}", content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/auth/logout").status_code, 405)

    def test_staff_does_not_imply_superuser(self):
        user = User.objects.create_user("staff@example.com", PASSWORD)
        user.is_staff = True
        user.save()
        self.assertFalse(user.has_perm("accounts.change_user"))

    def test_template_auth_is_rate_limited(self):
        for _ in range(10):
            self.client.post(
                "/signup?mode=signin",
                {"email": "nobody@example.com", "password": PASSWORD},
            )
        self.assertEqual(
            self.client.post(
                "/signup?mode=signin",
                {"email": "nobody@example.com", "password": PASSWORD},
            ).status_code,
            429,
        )


class GoalRoutingTests(TestCase):
    def test_multiple_goals_resume_independently(self):
        from accounts.onboarding import next_path

        user = User.objects.create_user("multi@example.com", PASSWORD, "Creator")
        user.email_verified_at = timezone.now()
        user.save()
        profile = user.profile
        profile.username = "multi"
        profile.country = "Nigeria"
        profile.bio = "Music"
        profile.genres = ["Afrobeats"]
        profile.goals = ["Plan a release", "Understand royalties"]
        profile.save()
        self.client.force_login(user)
        for step in ("role", "goals", "profile", "genres"):
            self.client.post("/setup/continue/" + step)
        user.refresh_from_db()
        self.assertEqual(next_path(user), "/royalty-setup")
        self.client.post("/setup/continue/royalties")
        user.refresh_from_db()
        self.assertEqual(next_path(user), "/release-setup")
        self.client.post("/setup/continue/release")
        user.refresh_from_db()
        self.assertIsNotNone(user.onboarding_completed_at)
        self.assertEqual(next_path(user), "/portal")
