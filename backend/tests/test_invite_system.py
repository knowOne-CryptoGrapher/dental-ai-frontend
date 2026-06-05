"""
Invite token lifecycle tests.

Covers: creation, RBAC on creation, validation, completion, token security,
ai_safety_logs entries, and pending-invite listing.

Run:
    cd backend && python -m pytest tests/test_invite_system.py -v
"""
import time
import uuid
import httpx
import pytest
from tests.conftest import (
    API_URL, DB, TERMS_VERSION, PRIVACY_POLICY_VERSION,
    create_practice, create_user, create_invite_token, cleanup_practice,
)


# ── Module fixture ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def invite_env():
    practice = create_practice("invites")
    admin    = create_user(practice, "admin")
    staff    = create_user(practice, "staff")
    provider = create_user(practice, "provider")
    yield {"practice": practice, "admin": admin, "staff": staff, "provider": provider}
    cleanup_practice(practice["practice_id"])


# ── Helpers ─────────────────────────────────────────────────────────────

def _invite_url(pid: str) -> str:
    return f"{API_URL}/api/practices/{pid}/staff/invite"


def _validate_url(token: str) -> str:
    return f"{API_URL}/api/invite/{token}"


def _complete_url(token: str) -> str:
    return f"{API_URL}/api/invite/{token}/complete"


def _complete_body(full_name: str = "Test Invitee") -> dict:
    return {
        "full_name": full_name,
        "password": "SecurePass1!",
        "accepted_terms_version": TERMS_VERSION,
        "accepted_privacy_version": PRIVACY_POLICY_VERSION,
    }


# ── Token creation ──────────────────────────────────────────────────────

class TestInviteCreation:

    def test_admin_can_create_staff_invite(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        r = httpx.post(
            _invite_url(pid),
            headers=invite_env["admin"]["headers"],
            json={"email": f"new-staff-{uuid.uuid4().hex[:6]}@test.local", "role": "staff"},
            timeout=10.0,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "invite_url" in body
        assert "token" in body
        assert body["expires_in_hours"] == 24
        assert "invite_url" in body["invite_url"]

    def test_admin_can_create_provider_invite(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        r = httpx.post(
            _invite_url(pid),
            headers=invite_env["admin"]["headers"],
            json={"email": f"new-prov-{uuid.uuid4().hex[:6]}@test.local", "role": "provider"},
            timeout=10.0,
        )
        assert r.status_code == 200

    def test_admin_can_create_auditor_invite(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        r = httpx.post(
            _invite_url(pid),
            headers=invite_env["admin"]["headers"],
            json={"email": f"new-aud-{uuid.uuid4().hex[:6]}@test.local", "role": "auditor"},
            timeout=10.0,
        )
        assert r.status_code == 200

    def test_admin_cannot_invite_with_role_admin(self, invite_env):
        """Admins must never be created through the invite flow."""
        pid = invite_env["practice"]["practice_id"]
        r = httpx.post(
            _invite_url(pid),
            headers=invite_env["admin"]["headers"],
            json={"email": f"evil-{uuid.uuid4().hex[:6]}@test.local", "role": "admin"},
            timeout=10.0,
        )
        assert r.status_code == 400, "role=admin invite must be rejected"

    def test_admin_cannot_invite_with_role_super_admin(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        r = httpx.post(
            _invite_url(pid),
            headers=invite_env["admin"]["headers"],
            json={"email": f"evil-{uuid.uuid4().hex[:6]}@test.local", "role": "super_admin"},
            timeout=10.0,
        )
        assert r.status_code == 400

    def test_staff_cannot_create_invite(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        r = httpx.post(
            _invite_url(pid),
            headers=invite_env["staff"]["headers"],
            json={"email": "x@test.local", "role": "staff"},
            timeout=10.0,
        )
        assert r.status_code == 403

    def test_provider_cannot_create_invite(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        r = httpx.post(
            _invite_url(pid),
            headers=invite_env["provider"]["headers"],
            json={"email": "y@test.local", "role": "staff"},
            timeout=10.0,
        )
        assert r.status_code == 403

    def test_invite_creation_logs_to_ai_safety(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        email = f"safetylog-{uuid.uuid4().hex[:6]}@test.local"
        httpx.post(
            _invite_url(pid),
            headers=invite_env["admin"]["headers"],
            json={"email": email, "role": "staff"},
            timeout=10.0,
        )
        log = DB.ai_safety_logs.find_one({
            "event_type": "staff_invite_created",
            "practice_id": pid,
            "target_email": email,
        })
        assert log is not None, "ai_safety_logs must have staff_invite_created event"

    def test_duplicate_active_user_email_rejected(self, invite_env):
        """Can't invite someone who is already an active user in the practice."""
        pid = invite_env["practice"]["practice_id"]
        existing_email = invite_env["staff"]["email"]
        r = httpx.post(
            _invite_url(pid),
            headers=invite_env["admin"]["headers"],
            json={"email": existing_email, "role": "staff"},
            timeout=10.0,
        )
        assert r.status_code == 409


# ── Token validation (GET /invite/{token}) ──────────────────────────────

class TestInviteValidation:

    def test_valid_token_returns_correct_fields(self, invite_env):
        practice = invite_env["practice"]
        email = f"validate-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(practice, "staff", email)
        r = httpx.get(_validate_url(token), timeout=10.0)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["valid"] is True
        assert body["email"] == email
        assert body["role"] == "staff"
        assert body["practice_name"] == practice["name"]

    def test_expired_token_returns_410(self, invite_env):
        token = create_invite_token(invite_env["practice"], "staff", expired=True)
        r = httpx.get(_validate_url(token), timeout=10.0)
        assert r.status_code == 410

    def test_used_token_returns_410(self, invite_env):
        token = create_invite_token(invite_env["practice"], "staff", used=True)
        r = httpx.get(_validate_url(token), timeout=10.0)
        assert r.status_code == 410

    def test_nonexistent_token_returns_404(self, invite_env):
        r = httpx.get(_validate_url(str(uuid.uuid4())), timeout=10.0)
        assert r.status_code == 404

    def test_invite_for_different_practice_not_leaked(self, invite_env):
        """A token scoped to a different practice is still valid — but it's
        impossible to use it to join another practice (tested in isolation file)."""
        other = create_practice("validate-other")
        try:
            token = create_invite_token(other, "staff")
            r = httpx.get(_validate_url(token), timeout=10.0)
            assert r.status_code == 200
            assert r.json()["practice_name"] == other["name"]
        finally:
            cleanup_practice(other["practice_id"])


# ── Token completion (POST /invite/{token}/complete) ────────────────────

class TestInviteCompletion:

    def test_valid_completion_creates_user(self, invite_env):
        email = f"complete-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "staff", email)
        r = httpx.post(_complete_url(token), json=_complete_body("New Staff Member"), timeout=15.0)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body
        assert body["user"]["role"] == "staff"
        assert body["user"]["email"] == email
        assert body["user"]["practice_id"] == invite_env["practice"]["practice_id"]

    def test_completed_token_is_marked_used(self, invite_env):
        email = f"used-mark-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "staff", email)
        httpx.post(_complete_url(token), json=_complete_body(), timeout=15.0)
        doc = DB.invite_tokens.find_one({"token": token})
        assert doc["used"] is True
        assert doc["used_at"] is not None

    def test_token_cannot_be_reused(self, invite_env):
        email = f"reuse-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "staff", email)
        httpx.post(_complete_url(token), json=_complete_body(), timeout=15.0)
        r2 = httpx.post(_complete_url(token), json=_complete_body("Second Attempt"), timeout=15.0)
        assert r2.status_code == 410, "Reused token must be rejected"

    def test_expired_token_completion_rejected(self, invite_env):
        token = create_invite_token(invite_env["practice"], "staff", expired=True)
        r = httpx.post(_complete_url(token), json=_complete_body(), timeout=10.0)
        assert r.status_code == 410

    def test_short_password_rejected(self, invite_env):
        email = f"shortpw-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "staff", email)
        body = _complete_body()
        body["password"] = "abc"
        r = httpx.post(_complete_url(token), json=body, timeout=10.0)
        assert r.status_code == 400

    def test_wrong_terms_version_rejected(self, invite_env):
        email = f"terms-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "staff", email)
        body = _complete_body()
        body["accepted_terms_version"] = "0.0"
        r = httpx.post(_complete_url(token), json=body, timeout=10.0)
        assert r.status_code == 400

    def test_wrong_privacy_version_rejected(self, invite_env):
        email = f"priv-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "staff", email)
        body = _complete_body()
        body["accepted_privacy_version"] = "99.0"
        r = httpx.post(_complete_url(token), json=body, timeout=10.0)
        assert r.status_code == 400

    def test_empty_full_name_rejected(self, invite_env):
        email = f"noname-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "staff", email)
        body = _complete_body()
        body["full_name"] = "   "
        r = httpx.post(_complete_url(token), json=body, timeout=10.0)
        assert r.status_code == 400

    def test_completion_logs_to_ai_safety(self, invite_env):
        email = f"log-complete-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "staff", email)
        httpx.post(_complete_url(token), json=_complete_body(), timeout=15.0)
        pid = invite_env["practice"]["practice_id"]
        log = DB.ai_safety_logs.find_one({
            "event_type": "staff_invite_completed",
            "practice_id": pid,
        })
        assert log is not None, "ai_safety_logs must record staff_invite_completed"

    def test_jwt_contains_correct_role(self, invite_env):
        email = f"jwtcheck-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "auditor", email)
        r = httpx.post(_complete_url(token), json=_complete_body(), timeout=15.0)
        assert r.status_code == 200
        jwt_token = r.json()["access_token"]
        # Verify the new token works and returns the correct role via /auth/me
        me = httpx.get(
            f"{API_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=10.0,
        )
        assert me.status_code == 200
        assert me.json()["role"] == "auditor"

    def test_created_user_inherits_practice_id(self, invite_env):
        email = f"pid-inherit-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(invite_env["practice"], "staff", email)
        r = httpx.post(_complete_url(token), json=_complete_body(), timeout=15.0)
        assert r.status_code == 200
        assert r.json()["user"]["practice_id"] == invite_env["practice"]["practice_id"]


# ── Admin: list pending invites ──────────────────────────────────────────

class TestListInvites:

    def test_admin_sees_pending_invites(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        # Seed a known-pending token
        email = f"pending-list-{uuid.uuid4().hex[:6]}@test.local"
        create_invite_token(invite_env["practice"], "staff", email)
        r = httpx.get(
            f"{API_URL}/api/practices/{pid}/staff/invites",
            headers=invite_env["admin"]["headers"],
            timeout=10.0,
        )
        assert r.status_code == 200
        emails = [i["email"] for i in r.json()]
        assert email in emails, "Pending invite must appear in the list"

    def test_used_invites_not_listed(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        email = f"used-hidden-{uuid.uuid4().hex[:6]}@test.local"
        create_invite_token(invite_env["practice"], "staff", email, used=True)
        r = httpx.get(
            f"{API_URL}/api/practices/{pid}/staff/invites",
            headers=invite_env["admin"]["headers"],
            timeout=10.0,
        )
        assert r.status_code == 200
        emails = [i["email"] for i in r.json()]
        assert email not in emails, "Used invite must not appear in the pending list"

    def test_expired_invites_not_listed(self, invite_env):
        pid = invite_env["practice"]["practice_id"]
        email = f"exp-hidden-{uuid.uuid4().hex[:6]}@test.local"
        create_invite_token(invite_env["practice"], "staff", email, expired=True)
        r = httpx.get(
            f"{API_URL}/api/practices/{pid}/staff/invites",
            headers=invite_env["admin"]["headers"],
            timeout=10.0,
        )
        assert r.status_code == 200
        emails = [i["email"] for i in r.json()]
        assert email not in emails, "Expired invite must not appear in the pending list"
