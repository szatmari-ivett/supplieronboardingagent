from app.config import settings
from app.connectors.faults import is_fault_enabled
from app.tools import service


def test_create_onboarding_happy_path():
    result = service.create_onboarding(
        name="NewOrganic Ltd",
        country="GB",
        vat_id="GB987654321",
        confirmed=True,
    )
    assert result["status"] == "created"
    assert result["onboarding"]["id"].startswith("ONB-")
    assert result["onboarding"]["phase"] == "cloud_compliance"
    assert isinstance(result["onboarding"]["phase"], str)


def test_create_onboarding_is_idempotent():
    first = service.create_onboarding(
        name="Idempotent Supplier",
        country="DE",
        vat_id="DE333333333",
        confirmed=True,
    )
    second = service.create_onboarding(
        name="Idempotent Supplier",
        country="DE",
        vat_id="DE333333333",
        confirmed=True,
    )
    assert first["status"] == "created"
    assert second["status"] == "existing"
    assert second["onboarding"]["id"] == first["onboarding"]["id"]


def test_aggregate_status_after_create():
    created = service.create_onboarding(
        name="Status Supplier",
        country="DE",
        vat_id="DE555555555",
        confirmed=True,
    )
    onboarding_id = created["onboarding"]["id"]
    status = service.aggregate_status(onboarding_id)
    assert status.onboarding_id == onboarding_id
    assert status.health.value == "healthy"


def test_aggregate_status_handles_legacy_naive_timestamps():
    import json

    from app.memory.store import process_store

    created = service.create_onboarding(
        name="Legacy Timestamp Supplier",
        country="DE",
        vat_id="DE666666666",
        confirmed=True,
    )
    onboarding_id = created["onboarding"]["id"]
    onboarding = process_store.get_onboarding(onboarding_id)
    payload = json.loads(onboarding.model_dump_json())
    payload["updated_at"] = "2020-01-01T00:00:00"
    with process_store._connect() as conn:
        conn.execute(
            "UPDATE onboardings SET payload = ?, updated_at = ? WHERE id = ?",
            (json.dumps(payload), "2020-01-01T00:00:00", onboarding_id),
        )

    status = service.aggregate_status(onboarding_id)
    assert status.onboarding_id == onboarding_id
    assert status.health.value == "stale"


def test_aggregate_status_not_found_message():
    from app.agent.graph import run_agent

    result = run_agent("What is the status of onboarding ONB-999?", session_id="status-not-found")
    assert "ONB-999" in result["response"]


def test_degraded_status_when_erp_fault(monkeypatch):
    monkeypatch.setattr(settings, "fault_erp", True)
    assert is_fault_enabled("erp") is True

    created = service.create_onboarding(
        name="Fault Supplier",
        country="DE",
        vat_id="DE444444444",
        confirmed=True,
    )
    assert created["status"] == "partial_failure"

    onboarding_id = created["onboarding"]["id"]
    status = service.aggregate_status(onboarding_id)
    assert status.health.value == "degraded"
