from app.connectors.base import ConnectorError, with_resilience
from app.connectors.faults import is_fault_enabled
from app.domain.models import Supplier
from app.domain.time_utils import utc_now

_erp_suppliers: dict[str, dict] = {}


class ERPConnector:
    system = "erp"

    def lookup_supplier(self, vat_id: str | None = None, name: str | None = None) -> dict | None:
        def _lookup() -> dict | None:
            if is_fault_enabled(self.system):
                raise ConnectorError(self.system, "ERP system unavailable", retryable=True)
            for record in _erp_suppliers.values():
                if vat_id and record.get("vat_id") == vat_id:
                    return record
                if name and record.get("name", "").lower() == name.lower():
                    return record
            return None

        return with_resilience(self.system, _lookup)

    def create_supplier(self, supplier: Supplier, idempotency_key: str) -> dict:
        def _create() -> dict:
            if is_fault_enabled(self.system):
                raise ConnectorError(self.system, "ERP system unavailable", retryable=True)
            if idempotency_key in _erp_suppliers:
                return _erp_suppliers[idempotency_key]
            record = {
                "erp_id": f"ERP-{len(_erp_suppliers) + 1:04d}",
                "name": supplier.name,
                "vat_id": supplier.vat_id,
                "country": supplier.country,
                "status": "master_data_created",
                "synced_at": utc_now().isoformat(),
            }
            _erp_suppliers[idempotency_key] = record
            return record

        return with_resilience(self.system, _create, idempotency_key=idempotency_key)

    def get_status(self, external_ref: str | None) -> dict:
        def _status() -> dict:
            if is_fault_enabled(self.system):
                raise ConnectorError(self.system, "ERP system unavailable", retryable=False)
            if not external_ref:
                return {"status": "not_started", "available": True}
            return {
                "status": "master_data_synced",
                "external_ref": external_ref,
                "available": True,
                "synced_at": utc_now().isoformat(),
            }

        return with_resilience(self.system, _status)
