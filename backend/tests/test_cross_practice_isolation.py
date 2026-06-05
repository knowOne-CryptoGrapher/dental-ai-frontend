"""
Cross-practice isolation tests for the new invite and RBAC features.

Verifies that:
  - An invite token created for Practice A cannot be used to join Practice B.
  - Practice A's admin cannot list or create invites for Practice B.
  - A user from Practice A cannot read Practice B's config, branding, or invites.
  - Practice A's appointments are not visible to Practice B's users.
  - Retell sync uses the practice's own agent_id, never another practice's.

Complements the existing test_multi_tenant_isolation.py (patients/appointments
scoping), focusing on the invite system and practice config isolation.

Run:
    cd backend && python -m pytest tests/test_cross_practice_isolation.py -v
"""
import uuid
import httpx
import pytest
from tests.conftest import (
    API_URL, DB, TERMS_VERSION, PRIVACY_POLICY_VERSION,
    create_practice, create_user, create_invite_token,
    create_appointment, cleanup_practice,
)


# ── Module fixture: two fully independent practices ──────────────────────

@pytest.fixture(scope="module")
def two_practices():
    pa = create_practice("xiso-alpha")
    pb = create_practice("xiso-beta")
    admin_a = create_user(pa, "admin")
    admin_b = create_user(pb, "admin")
    staff_a = create_user(pa, "staff")
    apt_a   = create_appointment(pa, "Patient Alpha")
    apt_b   = create_appointment(pb, "Patient Beta")
    yield {
        "pa": pa, "pb": pb,
        "admin_a": admin_a, "admin_b": admin_b,
        "staff_a": staff_a,
        "apt_a": apt_a, "apt_b": apt_b,
    }
    cleanup_practice(pa["practice_id"])
    cleanup_practice(pb["practice_id"])


# ── Invite isolation ─────────────────────────────────────────────────────

class TestInviteCrossPracticeIsolation:

    def test_admin_a_cannot_create_invite_for_practice_b(self, two_practices):
        """Admin A's JWT is scoped to Practice A — sending to Practice B's URL must 403."""
        pid_b = two_practices["pb"]["practice_id"]
        r = httpx.post(
            f"{API_URL}/api/practices/{pid_b}/staff/invite",
            headers=two_practices["admin_a"]["headers"],
            json={"email": f"leak-{uuid.uuid4().hex[:6]}@test.local", "role": "staff"},
            timeout=10.0,
        )
        assert r.status_code in (403, 404), (
            "Admin A must not create invites for Practice B"
        )

    def test_admin_a_cannot_list_invites_for_practice_b(self, two_practices):
        pid_b = two_practices["pb"]["practice_id"]
        r = httpx.get(
            f"{API_URL}/api/practices/{pid_b}/staff/invites",
            headers=two_practices["admin_a"]["headers"],
            timeout=10.0,
        )
        assert r.status_code in (403, 404)

    def test_token_from_practice_a_cannot_join_practice_b(self, two_practices):
        """A token scoped to Practice A points to Practice A's practice_id.
        Completing it always creates a user in Practice A — you cannot redirect it
        to Practice B. This is verified by checking the created user's practice_id."""
        email = f"xprac-{uuid.uuid4().hex[:6]}@test.local"
        token = create_invite_token(two_practices["pa"], "staff", email)
        r = httpx.post(
            f"{API_URL}/api/invite/{token}/complete",
            json={
                "full_name": "Cross Practice Attacker",
                "password": "SecurePass123!",
                "accepted_terms_version": TERMS_VERSION,
                "accepted_privacy_version": PRIVACY_POLICY_VERSION,
            },
            timeout=15.0,
        )
        assert r.status_code == 200
        created_user = r.json()["user"]
        assert created_user["practice_id"] == two_practices["pa"]["practice_id"], (
            "User must be created in Practice A, not B"
        )
        assert created_user["practice_id"] != two_practices["pb"]["practice_id"]

    def test_invite_token_shows_correct_practice_name(self, two_practices):
        token = create_invite_token(two_practices["pa"], "staff")
        r = httpx.get(f"{API_URL}/api/invite/{token}", timeout=10.0)
        assert r.status_code == 200
        assert r.json()["practice_name"] == two_practices["pa"]["name"]
        assert r.json()["practice_name"] != two_practices["pb"]["name"]


# ── Practice config isolation ────────────────────────────────────────────

class TestPracticeConfigIsolation:

    def test_admin_a_cannot_read_practice_b_config(self, two_practices):
        pid_b = two_practices["pb"]["practice_id"]
        r = httpx.get(
            f"{API_URL}/api/practice/{pid_b}/config",
            headers=two_practices["admin_a"]["headers"],
            timeout=10.0,
        )
        assert r.status_code in (403, 404)

    def test_admin_a_cannot_read_practice_b_branding(self, two_practices):
        pid_b = two_practices["pb"]["practice_id"]
        r = httpx.get(
            f"{API_URL}/api/practice/{pid_b}/branding",
            headers=two_practices["admin_a"]["headers"],
            timeout=10.0,
        )
        assert r.status_code in (403, 404)

    def test_admin_a_cannot_update_practice_b_branding(self, two_practices):
        pid_b = two_practices["pb"]["practice_id"]
        r = httpx.put(
            f"{API_URL}/api/practice/{pid_b}/branding",
            headers=two_practices["admin_a"]["headers"],
            json={
                "agent_name": "Hacker",
                "greeting": "Evil",
                "closing": "Evil",
                "voice_tone": "casual",
            },
            timeout=10.0,
        )
        assert r.status_code in (403, 404)

    def test_admin_a_cannot_read_practice_b_hours(self, two_practices):
        pid_b = two_practices["pb"]["practice_id"]
        r = httpx.get(
            f"{API_URL}/api/practice/{pid_b}/hours",
            headers=two_practices["admin_a"]["headers"],
            timeout=10.0,
        )
        assert r.status_code in (403, 404)

    def test_staff_a_cannot_read_practice_b_config(self, two_practices):
        pid_b = two_practices["pb"]["practice_id"]
        r = httpx.get(
            f"{API_URL}/api/practice/{pid_b}/config",
            headers=two_practices["staff_a"]["headers"],
            timeout=10.0,
        )
        assert r.status_code in (403, 404)


# ── Appointment isolation ────────────────────────────────────────────────

class TestAppointmentCrossPracticeIsolation:

    def test_staff_a_cannot_cancel_practice_b_appointment(self, two_practices):
        apt_b_id = two_practices["apt_b"]["appointment_id"]
        r = httpx.delete(
            f"{API_URL}/api/appointments/{apt_b_id}",
            headers=two_practices["staff_a"]["headers"],
            timeout=10.0,
        )
        assert r.status_code == 404, (
            "Staff A must get 404 on Practice B's appointment (not 403, to avoid enumeration)"
        )

    def test_admin_a_cannot_cancel_practice_b_appointment(self, two_practices):
        apt_b_id = two_practices["apt_b"]["appointment_id"]
        r = httpx.delete(
            f"{API_URL}/api/appointments/{apt_b_id}",
            headers=two_practices["admin_a"]["headers"],
            timeout=10.0,
        )
        assert r.status_code == 404

    def test_appointments_list_scoped_to_own_practice(self, two_practices):
        """GET /appointments for Admin A must only return Practice A's appointments."""
        r = httpx.get(
            f"{API_URL}/api/appointments",
            headers=two_practices["admin_a"]["headers"],
            timeout=10.0,
        )
        assert r.status_code == 200
        ids = {a["id"] for a in r.json()}
        apt_a_id = two_practices["apt_a"]["appointment_id"]
        apt_b_id = two_practices["apt_b"]["appointment_id"]
        assert apt_a_id in ids, "Practice A appointment must be visible to Admin A"
        assert apt_b_id not in ids, "LEAK: Practice B appointment visible to Admin A"


# ── Retell sync scoping ──────────────────────────────────────────────────

class TestRetellSyncIsolation:

    def test_branding_update_uses_own_practice_agent_id(self, two_practices):
        """Each practice's sync uses its own retell.agent_id, never another's.
        Set a fake agent_id on Practice A only — Practice B's sync must stay unaffected."""
        pa = two_practices["pa"]
        pb = two_practices["pb"]
        FAKE_AGENT = f"fake-agent-{uuid.uuid4().hex[:8]}"

        DB.practices.update_one(
            {"id": pa["practice_id"]},
            {"$set": {"settings.retell.agent_id": FAKE_AGENT}},
        )
        try:
            # Update branding on Practice A — should fail because fake agent
            r_a = httpx.put(
                f"{API_URL}/api/practice/{pa['practice_id']}/branding",
                headers=two_practices["admin_a"]["headers"],
                json={
                    "agent_name": "AgentA",
                    "greeting": "Hi from A",
                    "closing": "Bye from A",
                    "voice_tone": "warm_professional",
                },
                timeout=15.0,
            )
            assert r_a.status_code == 200
            assert r_a.json()["retell_sync"] == "failed"

            # Update branding on Practice B — should be skipped (no agent_id)
            r_b = httpx.put(
                f"{API_URL}/api/practice/{pb['practice_id']}/branding",
                headers=two_practices["admin_b"]["headers"],
                json={
                    "agent_name": "AgentB",
                    "greeting": "Hi from B",
                    "closing": "Bye from B",
                    "voice_tone": "warm_professional",
                },
                timeout=15.0,
            )
            assert r_b.status_code == 200
            assert r_b.json()["retell_sync"] == "skipped"

            # Verify ai_safety_logs has the correct agent_id for Practice A
            log = DB.ai_safety_logs.find_one({
                "event_type": "retell_sync",
                "practice_id": pa["practice_id"],
                "agent_id": FAKE_AGENT,
            })
            assert log is not None, "Sync log for Practice A must use its own agent_id"

            # Practice B's sync must not have the fake agent_id in its logs
            wrong_log = DB.ai_safety_logs.find_one({
                "event_type": "retell_sync",
                "practice_id": pb["practice_id"],
                "agent_id": FAKE_AGENT,
            })
            assert wrong_log is None, "Practice B's sync must never reference Practice A's agent_id"

        finally:
            # Reset Practice A's agent_id
            DB.practices.update_one(
                {"id": pa["practice_id"]},
                {"$set": {"settings.retell.agent_id": None}},
            )
