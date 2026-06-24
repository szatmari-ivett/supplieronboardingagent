from app.connectors.base import ConnectorError, with_resilience
from app.connectors.faults import is_fault_enabled
from app.domain.models import Supplier
from app.domain.time_utils import utc_now

_packages: dict[str, dict] = {}


class ProcurementConnector:
    system = "procurement"

    def create_onboarding_package(self, supplier: Supplier, idempotency_key: str) -> dict:
        def _create() -> dict:
            if is_fault_enabled(self.system):
                raise ConnectorError(self.system, "Procurement platform unavailable", retryable=True)
            if idempotency_key in _packages:
                return _packages[idempotency_key]
            record = {
                "package_id": f"PKG-{len(_packages) + 1:04d}",
                "supplier_name": supplier.name,
                "status": "package_created",
                "created_at": utc_now().isoformat(),
            }
            _packages[idempotency_key] = record
            return record

        return with_resilience(self.system, _create, idempotency_key=idempotency_key)

    def get_status(self, external_ref: str | None) -> dict:
        def _status() -> dict:
            if is_fault_enabled(self.system):
                raise ConnectorError(self.system, "Procurement platform unavailable", retryable=False)
            if not external_ref:
                return {"status": "not_started", "available": True}
            return {
                "status": "awaiting_documents",
                "external_ref": external_ref,
                "available": True,
                "synced_at": utc_now().isoformat(),
            }

        return with_resilience(self.system, _status)
