import json
import uuid
from django.test import TestCase, Client
from apiv1.tests import make_user
from network.test_mvp import creator
from network.models import CreatorConnection


class ResourceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.target = creator("target@example.com", "target")

    def post(self, path, data, key=None):
        return self.client.post(
            path,
            json.dumps(data),
            content_type="application/json",
            headers={"Idempotency-Key": str(key or uuid.uuid4())},
        )

    def test_mutation_retry_returns_same_response_and_conflicts_on_reuse(self):
        key = uuid.uuid4()
        first = self.post(
            "/api/v1/connections", {"recipient": str(self.target.pk)}, key
        )
        again = self.post(
            "/api/v1/connections", {"recipient": str(self.target.pk)}, key
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json(), again.json())
        self.assertEqual(CreatorConnection.objects.count(), 1)
        self.assertEqual(
            self.post(
                "/api/v1/connections", {"recipient": str(self.user.pk)}, key
            ).status_code,
            409,
        )

    def test_authenticated_paginated_reads(self):
        self.assertEqual(Client().get("/api/v1/connections").status_code, 401)
        result = self.client.get("/api/v1/connections").json()
        self.assertEqual(result["pagination"]["count"], 0)
        self.assertEqual(result["data"], [])

    def test_cross_account_thread_and_required_key(self):
        from network.services import request_connection, transition_connection

        outsider = creator("other@example.com", "other")
        row = request_connection(self.target, outsider)
        transition_connection(outsider, row, "accept")
        self.assertEqual(
            self.client.get(f"/api/v1/connections/{row.pk}/messages").status_code, 403
        )
        response = self.client.post(
            "/api/v1/connections", "{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "idempotency_key")
