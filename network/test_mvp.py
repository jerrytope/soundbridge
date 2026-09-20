import uuid
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from accounts.models import User
from network.models import CreatorConnection, DirectMessage
from network.services import (
    request_connection,
    transition_connection,
    block_user,
    send_message,
)


def creator(email, username):
    user = User.objects.create_user(email, "correcthorsebattery1", username)
    user.email_verified_at = timezone.now()
    user.save()
    profile = user.profile
    profile.username = username
    profile.country = "Nigeria"
    profile.bio = "Music creator"
    profile.skills = ["Mixing"]
    profile.published = True
    profile.save()
    return user


class NetworkTests(TestCase):
    def setUp(self):
        self.a = creator("a@example.com", "alice")
        self.b = creator("b@example.com", "bob")
        self.c = creator("c@example.com", "carol")

    def test_real_discovery_and_public_privacy(self):
        self.b.profile.city = "HiddenCity"
        self.b.profile.city_public = False
        self.b.profile.save()
        self.client.force_login(self.a)
        self.assertContains(self.client.get("/discover?skill=Mixing"), "bob")
        self.assertNotContains(self.client.get("/people/bob"), "HiddenCity")
        self.assertNotContains(
            self.client.get("/discover?city=HiddenCity"), "/people/bob"
        )

    def test_connection_actor_checks_and_idempotency(self):
        row = request_connection(self.a, self.b)
        self.assertEqual(request_connection(self.b, self.a).pk, row.pk)
        with self.assertRaises(PermissionDenied):
            transition_connection(self.a, row, "accept")
        with self.assertRaises(PermissionDenied):
            transition_connection(self.c, row, "accept")
        transition_connection(self.b, row, "accept")
        transition_connection(self.b, row, "accept")
        self.assertEqual(CreatorConnection.objects.count(), 1)

    def test_messaging_requires_acceptance_and_deduplicates(self):
        row = request_connection(self.a, self.b)
        key = uuid.uuid4()
        with self.assertRaises(PermissionDenied):
            send_message(self.a, row, "hello", key)
        row = transition_connection(self.b, row, "accept")
        send_message(self.a, row, "hello", key)
        send_message(self.a, row, "hello", key)
        self.assertEqual(DirectMessage.objects.count(), 1)
        with self.assertRaises(ValidationError):
            send_message(self.a, row, "changed", key)
        with self.assertRaises(PermissionDenied):
            send_message(self.c, row, "intruder", uuid.uuid4())
        self.client.force_login(self.c)
        self.assertEqual(self.client.get(f"/messages/{row.pk}").status_code, 403)
        block_user(self.b, self.a)
        with self.assertRaises(PermissionDenied):
            send_message(self.a, row, "blocked", uuid.uuid4())

    def test_legacy_put_cannot_delete_shared_data(self):
        row = request_connection(self.a, self.b)
        self.client.force_login(self.a)
        response = self.client.put(
            "/api/workspace",
            "{}",
            content_type="application/json",
            headers={"X-Soundbridge-Account": str(self.a.pk)},
        )
        self.assertEqual(response.status_code, 410)
        self.assertTrue(CreatorConnection.objects.filter(pk=row.pk).exists())


class CollaborationWorkflowTests(TestCase):
    def setUp(self):
        from network.models import Collaboration, Participant
        from datetime import timedelta

        self.a = creator("owner@example.com", "owner")
        self.b = creator("guest@example.com", "guest")
        self.c = creator("outsider@example.com", "outsider")
        self.project = Collaboration.objects.create(
            owner=self.a, title="EP", brief="Two songs"
        )
        self.invitation = Participant.objects.create(
            collaboration=self.project,
            user=self.b,
            display_name="Guest",
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_invitation_access_and_split_revisions(self):
        from network.collaboration_services import (
            invitation_response,
            propose_splits,
            respond_split,
        )

        self.client.force_login(self.b)
        self.assertEqual(
            self.client.get(f"/collaborations/{self.project.pk}").status_code, 403
        )
        invitation_response(self.b, self.invitation, "accept")
        self.assertEqual(
            self.client.get(f"/collaborations/{self.project.pk}").status_code, 200
        )
        shares = {str(self.a.pk): "60", str(self.b.pk): "40"}
        proposal = propose_splits(self.a, self.project, shares)
        respond_split(self.a, proposal, "acknowledged")
        respond_split(self.b, proposal, "acknowledged")
        proposal.refresh_from_db()
        self.assertEqual(proposal.state, "acknowledged")
        revised = propose_splits(self.a, self.project, shares)
        self.assertEqual(revised.responses.count(), 0)
        with self.assertRaises(ValidationError):
            respond_split(self.b, proposal, "acknowledged")
        with self.assertRaises(PermissionDenied):
            respond_split(self.c, revised, "acknowledged")

    def test_removed_participant_loses_file_access(self):
        from network.models import CollaborationFile
        from network.collaboration_services import invitation_response

        invitation_response(self.b, self.invitation, "accept")
        file = CollaborationFile.objects.create(
            collaboration=self.project,
            uploader=self.a,
            name="notes.txt",
            content=b"private",
            state="clean",
        )
        self.client.force_login(self.b)
        self.assertEqual(
            self.client.get(f"/collaborations/files/{file.pk}").status_code, 200
        )
        self.invitation.invitation_state = "expired"
        self.invitation.save()
        self.assertEqual(
            self.client.get(f"/collaborations/files/{file.pk}").status_code, 403
        )
        self.client.force_login(self.a)
        file.state = "quarantined"
        file.save()
        self.assertEqual(
            self.client.get(f"/collaborations/files/{file.pk}").status_code, 404
        )

    def test_expired_invitation_cannot_be_accepted(self):
        from network.collaboration_services import invitation_response

        self.invitation.expires_at = timezone.now()
        self.invitation.save()
        with self.assertRaises(ValidationError):
            invitation_response(self.b, self.invitation, "accept")
