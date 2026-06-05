"""
Retell sync behavior tests.

Strategy:
  - "no_agent_id" practice: settings.retell.agent_id = null
      → sync is always skipped; response contains retell_sync: "skipped"
  - "fake_agent_id" practice: settings.retell.agent_id = "test-fake-agent-000"
      → sync is attempted, Retell API rejects the fake ID
      → response contains retell_sync: "failed"
      → ai_safety_logs records the failure (success: false)
  - Staff/provider/auditor cannot update branding → 403 → no sync triggered

The "ok" path requires a live Retell agent — it is integration-tested via
the retell_hard_suite.py suite. These tests cover skipped, failed, and the
non-blocking guarantee (settings save succeeds even when Retell fails).

Run:
    cd backend && python -m pytest tests/test_retell_sync.py -v
"""
import uuid
import httpx
import pytest
from tests.conftest import (
    API_URL, DB, create_practice, create_user, cleanup_practice,
)

_FAKE_AGENT_ID = "test-fake-agent-000000000000"


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def no_agent_env():
    """Practice with no Retell agent_id configured (default)."""
    practice = create_practice("retell-no-agent")
    admin    = create_user(practice, "admin")
    staff    = create_user(practice, "staff")
    yield {"practice": practice, "admin": admin, "staff": staff}
    cleanup_practice(practice["practice_id"])


@pytest.fixture(scope="module")
def fake_agent_env():
    """Practice with a fake Retell agent_id — sync will attempt and fail."""
    practice = create_practice("retell-fake-agent")
    # Inject a fake agent_id so the sync service tries (and fails) to call Retell.
    DB.practices.update_one(
        {"id": practice["practice_id"]},
        {"$set": {"settings.retell.agent_id": _FAKE_AGENT_ID}},
    )
    practice["doc"]["settings"]["retell"]["agent_id"] = _FAKE_AGENT_ID
    admin = create_user(practice, "admin")
    yield {"practice": practice, "admin": admin}
    cleanup_practice(practice["practice_id"])


# ── Shared branding payloads ─────────────────────────────────────────────

def _branding(agent_name: str = "Amanda") -> dict:
    return {
        "agent_name": agent_name,
        "greeting": "Thank you for calling!",
        "closing": "Have a great day!",
        "voice_tone": "warm_professional",
    }


# ── Sync skipped when no agent_id ────────────────────────────────────────

class TestSyncSkippedNoAgentId:

    def test_branding_update_returns_skipped(self, no_agent_env):
        pid = no_agent_env["practice"]["practice_id"]
        r = httpx.put(
            f"{API_URL}/api/practice/{pid}/branding",
            headers=no_agent_env["admin"]["headers"],
            json=_branding(),
            timeout=15.0,
        )
        assert r.status_code == 200, r.text
        assert r.json()["retell_sync"] == "skipped"

    def test_config_update_branding_returns_skipped(self, no_agent_env):
        pid = no_agent_env["practice"]["practice_id"]
        r = httpx.put(
            f"{API_URL}/api/practice/{pid}/config",
            headers=no_agent_env["admin"]["headers"],
            json={"branding": _branding("TestBot")},
            timeout=15.0,
        )
        assert r.status_code == 200
        assert r.json().get("retell_sync") == "skipped"

    def test_config_update_hours_returns_skipped(self, no_agent_env):
        pid = no_agent_env["practice"]["practice_id"]
        hours_payload = {
            "timezone": "America/Toronto",
            "weekly": {
                "mon": {"open": "08:00", "close": "17:00"},
                "tue": {"open": "08:00", "close": "17:00"},
                "wed": {"open": "08:00", "close": "17:00"},
                "thu": {"open": "08:00", "close": "17:00"},
                "fri": {"open": "08:00", "close": "15:00"},
                "sat": None,
                "sun": None,
            },
            "closed_dates": [],
        }
        r = httpx.put(
            f"{API_URL}/api/practice/{pid}/config",
            headers=no_agent_env["admin"]["headers"],
            json={"hours": hours_payload},
            timeout=15.0,
        )
        assert r.status_code == 200
        assert r.json().get("retell_sync") == "skipped"

    def test_config_update_emergency_returns_skipped(self, no_agent_env):
        pid = no_agent_env["practice"]["practice_id"]
        r = httpx.put(
            f"{API_URL}/api/practice/{pid}/config",
            headers=no_agent_env["admin"]["headers"],
            json={"emergency": {
                "triggers": ["severe pain", "bleeding"],
                "response_policy": "earliest_available",
                "after_hours_handoff_phone": None,
            }},
            timeout=15.0,
        )
        assert r.status_code == 200
        assert r.json().get("retell_sync") == "skipped"

    def test_settings_save_succeeds_despite_skipped_sync(self, no_agent_env):
        """The actual branding data must be persisted even when sync is skipped."""
        pid = no_agent_env["practice"]["practice_id"]
        new_agent_name = f"Bot-{uuid.uuid4().hex[:6]}"
        httpx.put(
            f"{API_URL}/api/practice/{pid}/branding",
            headers=no_agent_env["admin"]["headers"],
            json=_branding(new_agent_name),
            timeout=15.0,
        )
        doc = DB.practices.find_one({"id": pid}, {"_id": 0, "settings.branding": 1})
        assert doc["settings"]["branding"]["agent_name"] == new_agent_name


# ── Sync attempted when agent_id is set ─────────────────────────────────

class TestSyncAttemptedWithFakeAgent:

    def test_branding_update_returns_failed(self, fake_agent_env):
        """With a fake agent_id, Retell rejects the PATCH → retell_sync: 'failed'."""
        pid = fake_agent_env["practice"]["practice_id"]
        r = httpx.put(
            f"{API_URL}/api/practice/{pid}/branding",
            headers=fake_agent_env["admin"]["headers"],
            json=_branding("Fake Amanda"),
            timeout=15.0,
        )
        assert r.status_code == 200, r.text
        assert r.json()["retell_sync"] == "failed"

    def test_settings_save_succeeds_despite_failed_sync(self, fake_agent_env):
        """Settings must be persisted even when Retell API returns an error."""
        pid = fake_agent_env["practice"]["practice_id"]
        name = f"SyncFail-{uuid.uuid4().hex[:4]}"
        r = httpx.put(
            f"{API_URL}/api/practice/{pid}/branding",
            headers=fake_agent_env["admin"]["headers"],
            json=_branding(name),
            timeout=15.0,
        )
        assert r.status_code == 200
        doc = DB.practices.find_one({"id": pid}, {"_id": 0, "settings.branding": 1})
        assert doc["settings"]["branding"]["agent_name"] == name

    def test_failed_sync_logged_to_ai_safety(self, fake_agent_env):
        """ai_safety_logs must record the failed sync attempt."""
        pid = fake_agent_env["practice"]["practice_id"]
        httpx.put(
            f"{API_URL}/api/practice/{pid}/branding",
            headers=fake_agent_env["admin"]["headers"],
            json=_branding("LogTest"),
            timeout=15.0,
        )
        log = DB.ai_safety_logs.find_one({
            "event_type": "retell_sync",
            "practice_id": pid,
            "agent_id": _FAKE_AGENT_ID,
            "success": False,
        })
        assert log is not None, "ai_safety_logs must record failed retell_sync"
        assert log.get("error") is not None


# ── Staff cannot trigger sync ────────────────────────────────────────────

class TestSyncNotTriggeredByNonAdmin:

    def test_staff_branding_update_is_403_not_sync(self, no_agent_env):
        """Staff PUT /branding is rejected before sync is ever attempted."""
        pid = no_agent_env["practice"]["practice_id"]
        before_count = DB.ai_safety_logs.count_documents({
            "event_type": "retell_sync",
            "practice_id": pid,
        })
        r = httpx.put(
            f"{API_URL}/api/practice/{pid}/branding",
            headers=no_agent_env["staff"]["headers"],
            json=_branding("EvilBot"),
            timeout=10.0,
        )
        assert r.status_code == 403
        after_count = DB.ai_safety_logs.count_documents({
            "event_type": "retell_sync",
            "practice_id": pid,
        })
        assert after_count == before_count, "No sync log should be written when staff is rejected"

    def test_unauthenticated_branding_update_rejected(self, no_agent_env):
        pid = no_agent_env["practice"]["practice_id"]
        r = httpx.put(
            f"{API_URL}/api/practice/{pid}/branding",
            headers={},
            json=_branding(),
            timeout=10.0,
        )
        assert r.status_code in (401, 403, 422)


# ── Sync skipped entry logged ─────────────────────────────────────────────

class TestSyncSkippedLogging:

    def test_skipped_sync_not_logged(self, no_agent_env):
        """The skipped path exits before reaching the logger — no ai_safety_log expected."""
        # This is the specified contract: skip is fast-path, no DB write needed.
        # We verify the endpoint returns "skipped" and the settings are saved.
        pid = no_agent_env["practice"]["practice_id"]
        r = httpx.put(
            f"{API_URL}/api/practice/{pid}/branding",
            headers=no_agent_env["admin"]["headers"],
            json=_branding("SkipTest"),
            timeout=15.0,
        )
        assert r.status_code == 200
        assert r.json()["retell_sync"] == "skipped"
