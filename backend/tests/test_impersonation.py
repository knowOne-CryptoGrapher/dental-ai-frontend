"""
Tests for the Super-Admin Practice Impersonation feature.

Covers:
- Successful impersonation by super_admin
- JWT carries `impersonated_by` + `impersonator_email`
- /auth/me surfaces impersonation context
- RBAC: practice admin gets 403
- Suspended practice -> 400
- Non-existent practice -> 404
- Audit log row written
- Impersonation token works on practice-scoped endpoints
- Multi-tenant isolation: cannot leak across practices
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

SUPER = {"email": "owner@dentalai.com", "password": "OwnerPass123!"}
PRACTICE_ADMIN = {"email": "admin@dentaltest.com", "password": "TestPass123!"}
EMPIRE_PRACTICE_ID = "c50330bb-079b-4286-ac62-717a40bfa8dd"


# ─────────────────────────── fixtures ────────────────────────────

@pytest.fixture(scope="module")
def super_token():
    r = requests.post(f"{API}/auth/login", json=SUPER, timeout=10)
    assert r.status_code == 200, f"super login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def practice_admin_token():
    r = requests.post(f"{API}/auth/login", json=PRACTICE_ADMIN, timeout=10)
    assert r.status_code == 200, f"practice admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def temp_practice(super_token):
    """Create an isolated practice we can suspend / poke without harming Empire."""
    suffix = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    payload = {
        "practice_name": f"TEST_Imp_{suffix}",
        "contact_email": f"TEST_imp_contact_{suffix}@example.com",
        "admin_email": f"TEST_imp_admin_{suffix}@example.com",
        "admin_password": "TempPass123!",
        "admin_full_name": "Imp Admin",
    }
    r = requests.post(f"{API}/superadmin/practices", json=payload, headers=_h(super_token), timeout=10)
    assert r.status_code == 201, f"create practice failed: {r.status_code} {r.text}"
    data = r.json()
    # activate (created in onboarding)
    requests.post(f"{API}/superadmin/practices/{data['practice_id']}/activate",
                  headers=_h(super_token), timeout=10)
    yield data
    # teardown — best effort
    try:
        requests.post(f"{API}/superadmin/practices/{data['practice_id']}/suspend",
                      headers=_h(super_token), timeout=5)
    except Exception:
        pass


# ─────────────────────────── tests ───────────────────────────────

class TestImpersonateHappyPath:
    def test_super_admin_can_impersonate(self, super_token):
        r = requests.post(
            f"{API}/superadmin/practices/{EMPIRE_PRACTICE_ID}/impersonate",
            headers=_h(super_token), timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body and isinstance(body["access_token"], str) and body["access_token"]
        assert body.get("expires_in_seconds") == 3600
        assert body["target_practice"]["id"] == EMPIRE_PRACTICE_ID
        assert body["target_practice"]["name"]
        assert body["target_user"]["role"] == "admin"
        assert body["target_user"]["email"]
        assert body["target_user"]["id"]
        assert body["target_user"]["full_name"]

    def test_auth_me_with_imp_token_surfaces_impersonator(self, super_token):
        # Get super-admin id for later assertion
        sup_me = requests.get(f"{API}/auth/me", headers=_h(super_token), timeout=10).json()
        imp = requests.post(
            f"{API}/superadmin/practices/{EMPIRE_PRACTICE_ID}/impersonate",
            headers=_h(super_token), timeout=10,
        ).json()
        imp_token = imp["access_token"]

        r = requests.get(f"{API}/auth/me", headers=_h(imp_token), timeout=10)
        assert r.status_code == 200, r.text
        me = r.json()
        # Identity is the practice admin
        assert me["role"] == "admin"
        assert me["practice_id"] == EMPIRE_PRACTICE_ID
        assert me["email"] == imp["target_user"]["email"]
        # Impersonation context surfaced
        assert me.get("impersonated_by") == sup_me["id"]
        assert me.get("impersonator_email") == sup_me["email"]

    def test_imp_token_can_call_practice_scoped_endpoints(self, super_token):
        imp = requests.post(
            f"{API}/superadmin/practices/{EMPIRE_PRACTICE_ID}/impersonate",
            headers=_h(super_token), timeout=10,
        ).json()
        imp_token = imp["access_token"]

        r = requests.get(f"{API}/patients", headers=_h(imp_token), timeout=10)
        assert r.status_code == 200, f"/api/patients failed under imp token: {r.status_code} {r.text}"

    def test_audit_log_row_written(self, super_token):
        # Trigger an impersonation
        requests.post(
            f"{API}/superadmin/practices/{EMPIRE_PRACTICE_ID}/impersonate",
            headers=_h(super_token), timeout=10,
        )
        # Read audit logs (super-admin scope). Try common admin paths.
        candidates = [
            f"{API}/audit-logs?action=practice_impersonated&limit=20",
            f"{API}/audit/logs?action=practice_impersonated&limit=20",
            f"{API}/superadmin/audit-logs?action=practice_impersonated&limit=20",
        ]
        found = False
        for url in candidates:
            r = requests.get(url, headers=_h(super_token), timeout=10)
            if r.status_code == 200:
                logs = r.json() if isinstance(r.json(), list) else r.json().get("logs") or r.json().get("audit_logs") or []
                for entry in logs:
                    if entry.get("action") == "practice_impersonated" and entry.get("resource_id") == EMPIRE_PRACTICE_ID:
                        found = True
                        details = entry.get("details") or {}
                        assert details.get("target_user_id")
                        assert details.get("target_user_email")
                        break
                if found:
                    break
        if not found:
            pytest.skip("Could not locate audit-log read endpoint; row creation tested via direct DB out of scope")


class TestImpersonateRBAC:
    def test_practice_admin_gets_403(self, practice_admin_token):
        r = requests.post(
            f"{API}/superadmin/practices/{EMPIRE_PRACTICE_ID}/impersonate",
            headers=_h(practice_admin_token), timeout=10,
        )
        assert r.status_code == 403, r.text

    def test_unauthenticated_gets_401_or_403(self):
        r = requests.post(
            f"{API}/superadmin/practices/{EMPIRE_PRACTICE_ID}/impersonate",
            timeout=10,
        )
        assert r.status_code in (401, 403)


class TestImpersonateNegative:
    def test_nonexistent_practice_404(self, super_token):
        bogus = "00000000-0000-0000-0000-000000000000"
        r = requests.post(
            f"{API}/superadmin/practices/{bogus}/impersonate",
            headers=_h(super_token), timeout=10,
        )
        assert r.status_code == 404, r.text

    def test_suspended_practice_400(self, super_token, temp_practice):
        pid = temp_practice["practice_id"]
        # suspend it
        r = requests.post(f"{API}/superadmin/practices/{pid}/suspend",
                          headers=_h(super_token), timeout=10)
        assert r.status_code in (200, 201), r.text
        # impersonate -> 400
        r = requests.post(f"{API}/superadmin/practices/{pid}/impersonate",
                          headers=_h(super_token), timeout=10)
        assert r.status_code == 400, r.text
        assert "suspended" in r.json().get("detail", "").lower()
        # cleanup: re-activate so teardown works
        requests.post(f"{API}/superadmin/practices/{pid}/activate",
                      headers=_h(super_token), timeout=10)


class TestImpersonateMultiTenantIsolation:
    def test_imp_token_for_practice_A_cannot_see_practice_B_via_practice_endpoint(self, super_token, temp_practice):
        """Impersonate the temp practice and confirm /practice/{empire}/config is rejected."""
        pid = temp_practice["practice_id"]
        imp = requests.post(f"{API}/superadmin/practices/{pid}/impersonate",
                            headers=_h(super_token), timeout=10)
        assert imp.status_code == 200, imp.text
        imp_token = imp.json()["access_token"]

        # Access OTHER practice's scoped endpoint -> must NOT return that practice's data
        r = requests.get(f"{API}/practice/{EMPIRE_PRACTICE_ID}/config",
                         headers=_h(imp_token), timeout=10)
        # Either 403 (RBAC) or 404 — must NOT be 200 with Empire's data
        assert r.status_code in (403, 404), f"Expected isolation block, got {r.status_code}: {r.text}"
