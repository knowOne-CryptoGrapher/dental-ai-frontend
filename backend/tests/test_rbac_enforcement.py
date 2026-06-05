"""
RBAC enforcement tests.

Verifies that:
  - Admin can access all practice-management endpoints.
  - Staff, provider, and auditor are rejected (403) from admin-only endpoints.
  - Staff and admin can cancel/verify appointments; provider and auditor cannot.

Run:
    cd backend && python -m pytest tests/test_rbac_enforcement.py -v
"""
import pytest
import httpx
from tests.conftest import (
    API_URL, create_practice, create_user,
    create_appointment, cleanup_practice,
)


# ── Module fixture ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rbac_env():
    """One practice with all four non-superadmin roles."""
    practice = create_practice("rbac")
    admin    = create_user(practice, "admin")
    staff    = create_user(practice, "staff")
    provider = create_user(practice, "provider")
    auditor  = create_user(practice, "auditor")
    apt      = create_appointment(practice)
    yield {
        "practice": practice,
        "practice_id": practice["practice_id"],
        "admin": admin,
        "staff": staff,
        "provider": provider,
        "auditor": auditor,
        "appointment_id": apt["appointment_id"],
    }
    cleanup_practice(practice["practice_id"])


# ── Helpers ─────────────────────────────────────────────────────────────

def get(path: str, headers: dict) -> httpx.Response:
    return httpx.get(f"{API_URL}{path}", headers=headers, timeout=10.0)


def put(path: str, headers: dict, body: dict) -> httpx.Response:
    return httpx.put(f"{API_URL}{path}", headers=headers, json=body, timeout=10.0)


def post(path: str, headers: dict, body: dict) -> httpx.Response:
    return httpx.post(f"{API_URL}{path}", headers=headers, json=body, timeout=10.0)


def delete(path: str, headers: dict) -> httpx.Response:
    return httpx.delete(f"{API_URL}{path}", headers=headers, timeout=10.0)


NON_ADMIN_ROLES = ("staff", "provider", "auditor")


# ── Practice config — admin-only endpoints ──────────────────────────────

class TestPracticeConfigRBAC:

    def test_admin_can_get_practice_config(self, rbac_env):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/config", rbac_env["admin"]["headers"])
        assert r.status_code == 200
        assert "settings" in r.json()

    @pytest.mark.parametrize("role", NON_ADMIN_ROLES)
    def test_non_admin_cannot_get_practice_config(self, rbac_env, role):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/config", rbac_env[role]["headers"])
        assert r.status_code == 403, f"{role} should be forbidden from GET /config"

    def test_admin_can_get_branding(self, rbac_env):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/branding", rbac_env["admin"]["headers"])
        assert r.status_code == 200

    @pytest.mark.parametrize("role", NON_ADMIN_ROLES)
    def test_non_admin_cannot_get_branding(self, rbac_env, role):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/branding", rbac_env[role]["headers"])
        assert r.status_code == 403, f"{role} should be forbidden from GET /branding"

    def test_admin_can_update_branding(self, rbac_env):
        pid = rbac_env["practice_id"]
        payload = {
            "agent_name": "Amanda",
            "greeting": "Hello from test!",
            "closing": "Goodbye from test!",
            "voice_tone": "warm_professional",
        }
        r = put(f"/api/practice/{pid}/branding", rbac_env["admin"]["headers"], payload)
        assert r.status_code == 200
        assert "retell_sync" in r.json()

    @pytest.mark.parametrize("role", NON_ADMIN_ROLES)
    def test_non_admin_cannot_update_branding(self, rbac_env, role):
        pid = rbac_env["practice_id"]
        payload = {
            "agent_name": "Hacker",
            "greeting": "Evil greeting",
            "closing": "Evil closing",
            "voice_tone": "casual",
        }
        r = put(f"/api/practice/{pid}/branding", rbac_env[role]["headers"], payload)
        assert r.status_code == 403, f"{role} should be forbidden from PUT /branding"

    def test_admin_can_get_hours(self, rbac_env):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/hours", rbac_env["admin"]["headers"])
        assert r.status_code == 200

    @pytest.mark.parametrize("role", NON_ADMIN_ROLES)
    def test_non_admin_cannot_get_hours(self, rbac_env, role):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/hours", rbac_env[role]["headers"])
        assert r.status_code == 403

    def test_admin_can_get_emergency_rules(self, rbac_env):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/emergency-rules", rbac_env["admin"]["headers"])
        assert r.status_code == 200

    @pytest.mark.parametrize("role", NON_ADMIN_ROLES)
    def test_non_admin_cannot_get_emergency_rules(self, rbac_env, role):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/emergency-rules", rbac_env[role]["headers"])
        assert r.status_code == 403

    def test_admin_can_get_appointment_types(self, rbac_env):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/appointment-types", rbac_env["admin"]["headers"])
        assert r.status_code == 200

    @pytest.mark.parametrize("role", NON_ADMIN_ROLES)
    def test_non_admin_cannot_get_appointment_types(self, rbac_env, role):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/appointment-types", rbac_env[role]["headers"])
        assert r.status_code == 403


# ── Invite endpoints — admin-only ───────────────────────────────────────

class TestInviteEndpointsRBAC:

    def test_admin_can_list_invites(self, rbac_env):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practices/{pid}/staff/invites", rbac_env["admin"]["headers"])
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.parametrize("role", NON_ADMIN_ROLES)
    def test_non_admin_cannot_list_invites(self, rbac_env, role):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practices/{pid}/staff/invites", rbac_env[role]["headers"])
        assert r.status_code == 403, f"{role} should not list invites"

    def test_admin_can_create_invite(self, rbac_env):
        pid = rbac_env["practice_id"]
        r = post(
            f"/api/practices/{pid}/staff/invite",
            rbac_env["admin"]["headers"],
            {"email": f"rbac-invitee-{pid[:6]}@testclinic.local", "role": "staff"},
        )
        assert r.status_code == 200
        assert "invite_url" in r.json()

    @pytest.mark.parametrize("role", NON_ADMIN_ROLES)
    def test_non_admin_cannot_create_invite(self, rbac_env, role):
        pid = rbac_env["practice_id"]
        r = post(
            f"/api/practices/{pid}/staff/invite",
            rbac_env[role]["headers"],
            {"email": f"evil-{role}@hack.local", "role": "staff"},
        )
        assert r.status_code == 403, f"{role} should not create invites"


# ── Team management — admin-only ────────────────────────────────────────

class TestTeamManagementRBAC:

    def test_admin_can_list_users(self, rbac_env):
        r = get("/api/practice/users", rbac_env["admin"]["headers"])
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.parametrize("role", NON_ADMIN_ROLES)
    def test_non_admin_cannot_list_users(self, rbac_env, role):
        r = get("/api/practice/users", rbac_env[role]["headers"])
        assert r.status_code == 403


# ── Appointment actions — staff + admin only ────────────────────────────

class TestAppointmentActionRBAC:

    def test_admin_and_staff_can_read_appointments(self, rbac_env):
        for role in ("admin", "staff", "provider", "auditor"):
            r = get("/api/appointments", rbac_env[role]["headers"])
            assert r.status_code == 200, f"{role} should be able to list appointments"

    def test_provider_cannot_cancel_appointment(self, rbac_env):
        apt_id = rbac_env["appointment_id"]
        r = delete(f"/api/appointments/{apt_id}", rbac_env["provider"]["headers"])
        assert r.status_code == 403

    def test_auditor_cannot_cancel_appointment(self, rbac_env):
        apt_id = rbac_env["appointment_id"]
        r = delete(f"/api/appointments/{apt_id}", rbac_env["auditor"]["headers"])
        assert r.status_code == 403

    def test_provider_cannot_verify_appointment(self, rbac_env):
        apt_id = rbac_env["appointment_id"]
        r = post(
            f"/api/appointments/{apt_id}/verify",
            rbac_env["provider"]["headers"],
            {"verified_by": "provider"},
        )
        assert r.status_code == 403

    def test_auditor_cannot_verify_appointment(self, rbac_env):
        apt_id = rbac_env["appointment_id"]
        r = post(
            f"/api/appointments/{apt_id}/verify",
            rbac_env["auditor"]["headers"],
            {"verified_by": "auditor"},
        )
        assert r.status_code == 403

    def test_staff_can_cancel_appointment(self, rbac_env):
        """Staff can cancel — create a fresh one so we don't break shared state."""
        from tests.conftest import create_appointment
        apt = create_appointment(rbac_env["practice"])
        r = delete(
            f"/api/appointments/{apt['appointment_id']}",
            rbac_env["staff"]["headers"],
        )
        assert r.status_code == 200

    def test_admin_can_cancel_appointment(self, rbac_env):
        from tests.conftest import create_appointment
        apt = create_appointment(rbac_env["practice"])
        r = delete(
            f"/api/appointments/{apt['appointment_id']}",
            rbac_env["admin"]["headers"],
        )
        assert r.status_code == 200


# ── Unauthenticated requests ─────────────────────────────────────────────

class TestUnauthenticatedRejected:

    def test_no_token_rejected_from_config(self, rbac_env):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practice/{pid}/config", {})
        assert r.status_code in (401, 403, 422)

    def test_no_token_rejected_from_invites(self, rbac_env):
        pid = rbac_env["practice_id"]
        r = get(f"/api/practices/{pid}/staff/invites", {})
        assert r.status_code in (401, 403, 422)
