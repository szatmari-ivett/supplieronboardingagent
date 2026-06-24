from app.connectors.base import ConnectorError, with_resilience
from app.connectors.faults import is_fault_enabled
from app.domain.models import Supplier
from app.domain.time_utils import utc_now

_workflows: dict[str, dict] = {}


class CloudConnector:
    system = "cloud"

    def trigger_compliance_workflow(self, supplier: Supplier, idempotency_key: str) -> dict:
        def _trigger() -> dict:
            if is_fault_enabled(self.system):
                raise ConnectorError(self.system, "Cloud compliance app unavailable", retryable=True)
            if idempotency_key in _workflows:
                return _workflows[idempotency_key]
            record = {
                "workflow_id": f"WF-{len(_workflows) + 1:04d}",
                "supplier_name": supplier.name,
                "status": "compliance_in_progress",
                "created_at": utc_now().isoformat(),
            }
            _workflows[idempotency_key] = record
            return record

        return with_resilience(self.system, _trigger, idempotency_key=idempotency_key)

    def get_status(self, external_ref: str | None) -> dict:
        def _status() -> dict:
            if is_fault_enabled(self.system):
                raise ConnectorError(self.system, "Cloud compliance app unavailable", retryable=False)
            if not external_ref:
                return {"status": "not_started", "available": True}
            return {
                "status": "documents_under_review",
                "external_ref": external_ref,
                "available": True,
                "synced_at": utc_now().isoformat(),
            }

        return with_resilience(self.system, _status)
