"""API contract tests, ported from server/backend.test.js and server/ai.test.js."""

import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from accounts.models import StoredImage, User
from aiteam.gateway import AiError, read_reply, validate_request
from apiv1.serializers import WorkspaceError, validate_workspace, workspace_for
from integrations import spotify

PASSWORD = "correcthorsebattery1"


def make_user(email="creator@example.com", name="Temi Test"):
    from django.utils import timezone

    user = User.objects.create_user(email=email, password=PASSWORD, name=name)
    user.onboarding_completed_at = timezone.now()
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at", "onboarding_completed_at"])
    return user


class AuthTests(TestCase):
    def test_signup_creates_account_and_session(self):
        response = self.client.post(
            "/api/auth/signup",
            json.dumps(
                {
                    "email": "new@example.com",
                    "password": PASSWORD,
                    "name": "New Creator",
                    "consent": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], "new@example.com")
        self.assertEqual(payload["workspace"]["profile"]["name"], "New Creator")
        self.assertEqual(payload["revision"], 0)

    def test_short_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/signup",
            json.dumps({"email": "a@example.com", "password": "short", "name": "A"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("12", response.json()["error"])

    def test_duplicate_email_is_rejected(self):
        make_user("taken@example.com")
        response = self.client.post(
            "/api/auth/signup",
            json.dumps(
                {"email": "taken@example.com", "password": PASSWORD, "name": "Other"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_wrong_password_gives_one_message(self):
        make_user()
        response = self.client.post(
            "/api/auth/login",
            json.dumps(
                {"email": "creator@example.com", "password": "wrongpassword12345"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "Email or password is incorrect.")

    @override_settings(ALLOW_SIGNUP=False)
    def test_registration_can_be_closed(self):
        response = self.client.post(
            "/api/auth/signup",
            json.dumps({"email": "x@example.com", "password": PASSWORD, "name": "X"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_session_is_revoked_on_logout(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(
            "/api/auth/logout",
            "{}",
            content_type="application/json",
            headers={"x-soundbridge-account": str(user.id)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.get("/api/auth/session").json()["user"])


class WorkspaceApiTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.headers = {"x-soundbridge-account": str(self.user.id)}

    def _state(self, **overrides):
        state = workspace_for(self.user)
        state.update(overrides)
        return state

    def test_requires_sign_in(self):
        self.assertEqual(Client().get("/api/workspace").status_code, 401)

    def test_workspace_replacement_is_retired(self):
        response = self.client.put(
            "/api/workspace",
            json.dumps({"workspace": self._state(), "revision": 0}),
            content_type="application/json",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 410)
        self.user.refresh_from_db()
        self.assertEqual(self.user.workspace_revision, 0)

    def test_account_header_must_match(self):
        response = self.client.put(
            "/api/workspace",
            "{}",
            content_type="application/json",
            headers={"x-soundbridge-account": "someone-else"},
        )
        self.assertEqual(response.status_code, 409)

    def test_legacy_read_still_returns_owned_data(self):
        from releases.models import ReleaseProject

        ReleaseProject.objects.create(
            owner=self.user, title="Night Drive", date="2026-11-20"
        )
        saved = self.client.get("/api/workspace").json()["workspace"]["releases"][0]
        self.assertEqual(saved["title"], "Night Drive")


class WorkspaceValidationTests(TestCase):
    def _validate(self, state):
        return validate_workspace(state, "creator@example.com", lambda url: False)

    def test_missing_name_is_rejected(self):
        with self.assertRaises(WorkspaceError):
            self._validate({"profile": {"name": "  "}, **{key: [] for key in _ARRAYS}})

    def test_bad_release_type_is_rejected(self):
        state = _blank()
        state["releases"] = [
            {
                "id": "a",
                "title": "X",
                "type": "Mixtape",
                "date": "2026-01-01",
                "tasks": [],
            }
        ]
        with self.assertRaises(WorkspaceError):
            self._validate(state)

    def test_unsupported_currency_is_rejected(self):
        state = _blank()
        state["statements"] = [
            {
                "id": "a",
                "name": "s.csv",
                "rows": [
                    {"track": "t", "platform": "p", "amount": 1, "currency": "JPY"}
                ],
            }
        ]
        with self.assertRaises(WorkspaceError):
            self._validate(state)

    def test_foreign_image_is_rejected(self):
        state = _blank()
        state["profile"]["photo"] = "/api/images/not-mine"
        with self.assertRaises(WorkspaceError):
            self._validate(state)

    def test_portfolio_must_be_http(self):
        state = _blank()
        state["profile"]["portfolio"] = "javascript:alert(1)"
        with self.assertRaises(WorkspaceError):
            self._validate(state)


_ARRAYS = [
    "connections",
    "projects",
    "applications",
    "releases",
    "statements",
    "calculations",
    "drafts",
    "aiConversations",
    "aiDeliverables",
    "royaltySources",
]


def _blank():
    return {
        "profile": {
            "name": "Creator",
            "role": "Artist",
            "city": "",
            "bio": "",
            "photo": "",
            "genres": [],
            "goals": [],
        },
        **{key: [] for key in _ARRAYS},
    }


class ImageTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user("other@example.com", "Other")
        self.client.force_login(self.user)
        self.headers = {"x-soundbridge-account": str(self.user.id)}

    def _upload(self):
        from io import BytesIO

        from PIL import Image as PilImage

        buffer = BytesIO()
        PilImage.new("RGB", (900, 300), (200, 40, 90)).save(buffer, format="PNG")
        import base64

        data_url = "data:image/png;base64," + base64.b64encode(
            buffer.getvalue()
        ).decode("ascii")
        return self.client.post(
            "/api/images",
            json.dumps({"image": data_url}),
            content_type="application/json",
            headers=self.headers,
        )

    def test_upload_resizes_and_stores_jpeg(self):
        response = self._upload()
        self.assertEqual(response.status_code, 201)
        image = StoredImage.objects.get(user=self.user)
        from io import BytesIO

        from PIL import Image as PilImage

        with PilImage.open(BytesIO(bytes(image.bytes))) as stored:
            self.assertEqual(stored.format, "JPEG")
            self.assertLessEqual(max(stored.size), 640)

    def test_other_accounts_cannot_read_an_image(self):
        url = self._upload().json()["url"]
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_rejects_non_image_payload(self):
        response = self.client.post(
            "/api/images",
            json.dumps({"image": "data:text/plain;base64,aGk="}),
            content_type="application/json",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)


class AiRequestTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.body = {
            "agentId": "manager",
            "context": {"artist": {"name": "Temi"}},
            "messages": [{"role": "user", "content": "Plan my release."}],
        }

    def test_unknown_agent_is_rejected(self):
        with self.assertRaises(AiError):
            validate_request({**self.body, "agentId": "nobody"})

    def test_last_message_must_be_from_the_creator(self):
        with self.assertRaises(AiError):
            validate_request(
                {**self.body, "messages": [{"role": "assistant", "content": "Hello"}]}
            )

    def test_too_many_messages_is_rejected(self):
        with self.assertRaises(AiError):
            validate_request(
                {**self.body, "messages": [{"role": "user", "content": "hi"}] * 41}
            )

    def test_reply_is_validated(self):
        payload = {
            "status": "completed",
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "answer": "Here is a plan.",
                                    "actions": ["Book a session"],
                                }
                            ),
                        }
                    ]
                }
            ],
        }
        self.assertEqual(
            read_reply(payload),
            {"content": "Here is a plan.", "actions": ["Book a session"]},
        )

    def test_unreadable_reply_is_rejected(self):
        payload = {
            "output": [{"content": [{"type": "output_text", "text": "not json"}]}]
        }
        with self.assertRaises(AiError):
            read_reply(payload)

    def test_chat_requires_configuration(self):
        response = self.client.post(
            "/api/ai/chat",
            json.dumps(self.body),
            content_type="application/json",
            headers={"x-soundbridge-account": str(self.user.id)},
        )
        self.assertEqual(response.status_code, 503)

    @override_settings(
        OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1", AI_DAILY_LIMIT=1
    )
    def test_daily_allowance_is_enforced(self):
        reply = {"content": "A plan.", "actions": []}
        headers = {"x-soundbridge-account": str(self.user.id)}
        with patch("apiv1.views.get_reply", return_value=reply):
            first = self.client.post(
                "/api/ai/chat",
                json.dumps(self.body),
                content_type="application/json",
                headers=headers,
            )
            second = self.client.post(
                "/api/ai/chat",
                json.dumps(self.body),
                content_type="application/json",
                headers=headers,
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)


class SpotifyTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_not_configured_reports_clearly(self):
        response = self.client.get("/api/music/search?q=burna")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Spotify is not connected", response.json()["error"])

    @override_settings(SPOTIFY_CLIENT_ID="id", SPOTIFY_CLIENT_SECRET="secret")
    def test_search_maps_results(self):
        class FakeResponse:
            def __init__(self, payload, status=200):
                self._payload = payload
                self.status_code = status
                self.headers = {}

            def json(self):
                return self._payload

        class FakeSession:
            def post(self, *args, **kwargs):
                return FakeResponse({"access_token": "token", "expires_in": 3600})

            def get(self, *args, **kwargs):
                return FakeResponse(
                    {
                        "artists": {
                            "items": [
                                {
                                    "id": "1",
                                    "name": "Test Artist",
                                    "external_urls": {
                                        "spotify": "https://open.spotify.com/artist/1"
                                    },
                                    "artists": [],
                                }
                            ]
                        }
                    }
                )

        spotify._token = None
        spotify._expires = 0
        result = spotify.search("test", "artist", "NG", session=FakeSession())
        self.assertEqual(result["items"][0]["name"], "Test Artist")
        self.assertEqual(result["items"][0]["url"], "https://open.spotify.com/artist/1")

    @override_settings(SPOTIFY_CLIENT_ID="id", SPOTIFY_CLIENT_SECRET="secret")
    def test_invalid_market_is_rejected(self):
        with self.assertRaises(spotify.SpotifyError):
            spotify.search("test", "artist", "nigeria")


class HealthTests(TestCase):
    def test_health_reports_storage(self):
        payload = self.client.get("/api/health").json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["storage"], "sqlite")
