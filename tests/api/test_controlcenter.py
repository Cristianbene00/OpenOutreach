"""Control center API tests — auth, scoping, settings, run control, queue."""
import pytest
from rest_framework.test import APIClient

from linkedin.models import Campaign, OutboundMessage, SiteConfig


@pytest.fixture
def client():
    return APIClient()


def _signup(client, username="alice", password="sup3rsecretpw!"):
    r = client.post(
        "/api/auth/signup",
        {"username": username, "password": password},
        format="json",
    )
    assert r.status_code == 201, r.content
    return r


@pytest.mark.django_db
class TestAuth:
    def test_signup_login_logout_me(self, client):
        _signup(client)
        # me works while logged in
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        assert r.json()["user"]["username"] == "alice"
        assert r.json()["user"]["is_staff"] is False  # not admin

        client.post("/api/auth/logout")
        r = client.get("/api/auth/me")
        assert r.status_code in (401, 403)

        r = client.post(
            "/api/auth/login",
            {"username": "alice", "password": "sup3rsecretpw!"},
            format="json",
        )
        assert r.status_code == 200

    def test_login_bad_password(self, client):
        _signup(client)
        client.post("/api/auth/logout")
        r = client.post(
            "/api/auth/login",
            {"username": "alice", "password": "wrong"},
            format="json",
        )
        assert r.status_code == 400

    def test_anonymous_blocked(self, client):
        assert client.get("/api/dashboard").status_code in (401, 403)


@pytest.mark.django_db
class TestLLMSettings:
    def test_key_masked_on_read(self, client):
        _signup(client)
        r = client.put(
            "/api/settings/llm",
            {"llm_provider": "openai", "ai_model": "gpt-4o", "llm_api_key": "sk-secret"},
            format="json",
        )
        assert r.status_code == 200
        body = r.json()
        assert "llm_api_key" not in body  # never echoed back
        assert body["llm_api_key_set"] is True
        assert SiteConfig.load().llm_api_key == "sk-secret"

    def test_blank_key_does_not_wipe(self, client):
        _signup(client)
        client.put(
            "/api/settings/llm",
            {"llm_provider": "openai", "ai_model": "gpt-4o", "llm_api_key": "sk-secret"},
            format="json",
        )
        client.put(
            "/api/settings/llm",
            {"llm_provider": "anthropic", "ai_model": "claude", "llm_api_key": ""},
            format="json",
        )
        assert SiteConfig.load().llm_api_key == "sk-secret"


@pytest.mark.django_db
class TestCampaignsAndScoping:
    def test_create_adds_creator_and_scopes(self, client):
        _signup(client, "alice")
        r = client.post("/api/campaigns", {"name": "Alice ICP"}, format="json")
        assert r.status_code == 201
        cid = r.json()["id"]
        assert client.get("/api/campaigns").json()[0]["name"] == "Alice ICP"

        # second user can't see it
        bob = APIClient()
        _signup(bob, "bob")
        assert bob.get("/api/campaigns").json() == []
        assert bob.get(f"/api/campaigns/{cid}").status_code == 404

    def test_start_stop_flips_enabled(self, client):
        _signup(client)
        cid = client.post("/api/campaigns", {"name": "C"}, format="json").json()["id"]
        assert Campaign.objects.get(pk=cid).enabled is False
        client.post(f"/api/campaigns/{cid}/start")
        assert Campaign.objects.get(pk=cid).enabled is True
        client.post(f"/api/campaigns/{cid}/stop")
        assert Campaign.objects.get(pk=cid).enabled is False


@pytest.mark.django_db
class TestQueue:
    def _make_pending_message(self, user):
        from crm.models import Deal, Lead

        n = OutboundMessage.objects.count()
        campaign = Campaign.objects.create(name=f"Q{n}", enabled=True, auto_send=False)
        campaign.users.add(user)
        lead = Lead.objects.create(
            linkedin_url=f"https://www.linkedin.com/in/jdoe{n}",
            public_identifier=f"jdoe{n}",
        )
        deal = Deal.objects.create(lead=lead, campaign=campaign)
        return OutboundMessage.objects.create(
            campaign=campaign, lead=lead, deal=deal,
            kind=OutboundMessage.Kind.FOLLOW_UP, body="hi",
            status=OutboundMessage.Status.PENDING_APPROVAL,
        )

    def test_approve_and_reject(self, client):
        from django.contrib.auth.models import User

        _signup(client, "alice")
        user = User.objects.get(username="alice")
        msg = self._make_pending_message(user)

        r = client.get("/api/queue?status=pending_approval")
        assert len(r.json()) == 1

        r = client.post(f"/api/queue/{msg.id}/approve", {"body": "hello!"}, format="json")
        assert r.status_code == 200
        msg.refresh_from_db()
        assert msg.status == OutboundMessage.Status.APPROVED
        assert msg.body == "hello!"

        # can't approve again
        assert client.post(f"/api/queue/{msg.id}/approve").status_code == 400

        # reject a fresh pending one
        msg2 = self._make_pending_message(user)
        r = client.post(f"/api/queue/{msg2.id}/reject")
        assert r.status_code == 200
        msg2.refresh_from_db()
        assert msg2.status == OutboundMessage.Status.REJECTED

    def test_queue_scoped_to_user(self, client):
        from django.contrib.auth.models import User

        _signup(client, "alice")
        self._make_pending_message(User.objects.get(username="alice"))
        bob = APIClient()
        _signup(bob, "bob")
        assert bob.get("/api/queue").json() == []
