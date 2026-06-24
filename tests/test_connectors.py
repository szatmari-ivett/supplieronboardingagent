import pytest

from app.connectors.base import ConnectorError, with_resilience
from app.connectors.erp import ERPConnector
from app.domain.models import Supplier


def test_idempotent_erp_create():
    connector = ERPConnector()
    supplier = Supplier(name="Idempotent Supplier", vat_id="DE333333333", country="DE")
    first = connector.create_supplier(supplier, "same-key")
    second = connector.create_supplier(supplier, "same-key")
    assert first["erp_id"] == second["erp_id"]


def test_retry_on_retryable_error(monkeypatch):
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ConnectorError("erp", "temporary", retryable=True)
        return "ok"

    result = with_resilience("erp", flaky, idempotency_key="retry-key")
    assert result == "ok"
    assert attempts["count"] == 2


def test_retry_stops_on_non_retryable_error():
    def fail():
        raise ConnectorError("erp", "permanent", retryable=False)

    with pytest.raises(ConnectorError):
        with_resilience("erp", fail)


def test_timeout_is_retryable(monkeypatch):
    import time

    monkeypatch.setattr("app.connectors.base.settings.connector_timeout_seconds", 0.1)
    monkeypatch.setattr("app.connectors.base.settings.connector_max_retries", 1)

    def slow():
        time.sleep(0.5)
        return "ok"

    with pytest.raises(ConnectorError) as exc:
        with_resilience("erp", slow)

    assert "timed out" in str(exc.value).lower()
    assert exc.value.retryable is True
