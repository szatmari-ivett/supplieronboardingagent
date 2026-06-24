import logging
from datetime import timedelta

from app.connectors.base import ConnectorError
from app.connectors.cloud import CloudConnector
from app.connectors.erp import ERPConnector
from app.connectors.procurement import ProcurementConnector
from app.domain.matching import find_duplicate_candidates
from app.domain.models import (
    AggregatedStatus,
    DuplicateCheckResult,
    HealthStatus,
    Onboarding,
    OnboardingPhase,
    Supplier,
    SystemStatus,
    TaskStatus,
)
from app.domain.time_utils import ensure_utc, utc_now
from app.memory.store import create_onboarding_record, process_store

logger = logging.getLogger(__name__)

erp = ERPConnector()
procurement = ProcurementConnector()
cloud = CloudConnector()

PHASE_ORDER = [
    OnboardingPhase.INITIATED,
    OnboardingPhase.DUPLICATE_CHECK,
    OnboardingPhase.PACKAGE_CREATED,
    OnboardingPhase.ERP_SYNC,
    OnboardingPhase.CLOUD_COMPLIANCE,
    OnboardingPhase.ACTIVE,
]


def duplicate_check(
    name: str,
    vat_id: str | None = None,
    country: str = "DE",
    address: str | None = None,
) -> DuplicateCheckResult:
    query = Supplier(name=name, vat_id=vat_id, country=country, address=address)
    return find_duplicate_candidates(query)


def create_onboarding(
    name: str,
    country: str,
    vat_id: str | None = None,
    address: str | None = None,
    confirmed: bool = False,
) -> dict:
    supplier = Supplier(name=name, vat_id=vat_id, country=country, address=address)
    duplicate = find_duplicate_candidates(supplier)

    if duplicate.is_duplicate and not confirmed:
        return {
            "status": "blocked",
            "reason": "Potential duplicate supplier detected. Confirmation required.",
            "duplicate_check": duplicate.model_dump(mode="json"),
            "requires_confirmation": True,
        }

    if duplicate.requires_review and not confirmed:
        return {
            "status": "blocked",
            "reason": "Potential duplicate requires human review before onboarding.",
            "duplicate_check": duplicate.model_dump(mode="json"),
            "requires_confirmation": True,
        }

    idempotency_key = f"{normalize_key(name)}:{vat_id or country}"
    existing = process_store.get_by_idempotency_key(idempotency_key)
    if existing:
        return {"status": "existing", "onboarding": existing.model_dump(mode="json"), "idempotent": True}

    onboarding = create_onboarding_record(supplier, idempotency_key)
    onboarding.phase = OnboardingPhase.DUPLICATE_CHECK
    _set_task_status(onboarding, "task-dup", TaskStatus.DONE)

    package = procurement.create_onboarding_package(supplier, idempotency_key)
    _set_task_status(onboarding, "task-proc", TaskStatus.DONE, package["package_id"])
    onboarding.phase = OnboardingPhase.PACKAGE_CREATED

    try:
        erp_record = erp.create_supplier(supplier, idempotency_key)
        _set_task_status(onboarding, "task-erp", TaskStatus.DONE, erp_record["erp_id"])
        onboarding.phase = OnboardingPhase.ERP_SYNC
    except ConnectorError as exc:
        _set_task_status(onboarding, "task-erp", TaskStatus.FAILED, error=str(exc))
        onboarding.phase = OnboardingPhase.FAILED
        process_store.save_onboarding(onboarding)
        return {
            "status": "partial_failure",
            "onboarding": onboarding.model_dump(mode="json"),
            "error": str(exc),
            "retryable": exc.retryable,
        }

    try:
        workflow = cloud.trigger_compliance_workflow(supplier, idempotency_key)
        _set_task_status(onboarding, "task-cloud", TaskStatus.IN_PROGRESS, workflow["workflow_id"])
        onboarding.phase = OnboardingPhase.CLOUD_COMPLIANCE
    except ConnectorError as exc:
        _set_task_status(onboarding, "task-cloud", TaskStatus.WAITING_EXTERNAL, error=str(exc))
        onboarding.phase = OnboardingPhase.ERP_SYNC

    process_store.save_onboarding(onboarding)
    return {"status": "created", "onboarding": onboarding.model_dump(mode="json"), "package": package}


def aggregate_status(onboarding_id: str) -> AggregatedStatus:
    onboarding = process_store.get_onboarding(onboarding_id)
    if not onboarding:
        raise ValueError(f"Onboarding {onboarding_id} not found")

    systems: list[SystemStatus] = []
    unavailable = 0

    for task in onboarding.tasks:
        if task.system == "agent":
            continue
        try:
            connector = {"erp": erp, "procurement": procurement, "cloud": cloud}[task.system]
            payload = connector.get_status(task.external_ref)
            systems.append(
                SystemStatus(
                    system=task.system,
                    status=payload.get("status", "unknown"),
                    phase=_map_task_to_phase(task),
                    available=payload.get("available", True),
                    detail=task.error,
                )
            )
        except ConnectorError as exc:
            unavailable += 1
            systems.append(
                SystemStatus(
                    system=task.system,
                    status="unavailable",
                    phase=_map_task_to_phase(task),
                    available=False,
                    detail=str(exc),
                )
            )

    health = HealthStatus.HEALTHY
    if unavailable:
        health = HealthStatus.DEGRADED
    elif ensure_utc(onboarding.updated_at) < utc_now() - timedelta(hours=24):
        health = HealthStatus.STALE

    summary = _build_summary(onboarding, systems, health)
    next_steps = _next_steps(onboarding, systems)

    return AggregatedStatus(
        onboarding_id=onboarding.id,
        supplier_name=onboarding.supplier.name,
        canonical_phase=onboarding.phase,
        health=health,
        systems=systems,
        summary=summary,
        next_steps=next_steps,
        metadata={"tasks": [task.model_dump(mode="json") for task in onboarding.tasks]},
    )


def normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _set_task_status(
    onboarding: Onboarding,
    task_id: str,
    status: TaskStatus,
    external_ref: str | None = None,
    error: str | None = None,
) -> None:
    for task in onboarding.tasks:
        if task.id == task_id:
            task.status = status
            task.external_ref = external_ref or task.external_ref
            task.error = error
            task.updated_at = utc_now()
            break


def _map_task_to_phase(task) -> OnboardingPhase:
    mapping = {
        "task-proc": OnboardingPhase.PACKAGE_CREATED,
        "task-erp": OnboardingPhase.ERP_SYNC,
        "task-cloud": OnboardingPhase.CLOUD_COMPLIANCE,
    }
    return mapping.get(task.id, OnboardingPhase.INITIATED)


def _build_summary(onboarding: Onboarding, systems: list[SystemStatus], health: HealthStatus) -> str:
    if health == HealthStatus.DEGRADED:
        down = ", ".join(item.system for item in systems if not item.available)
        return (
            f"Onboarding {onboarding.id} for {onboarding.supplier.name} is in phase "
            f"{onboarding.phase.value}, but status is degraded because {down} is unavailable."
        )
    return f"Onboarding {onboarding.id} for {onboarding.supplier.name} is currently in phase {onboarding.phase.value}."


def _next_steps(onboarding: Onboarding, systems: list[SystemStatus]) -> list[str]:
    steps: list[str] = []
    if any(not item.available for item in systems):
        steps.append("Retry failed system integrations once services recover.")
    if onboarding.phase == OnboardingPhase.CLOUD_COMPLIANCE:
        steps.append("Monitor cloud compliance workflow until documents are approved.")
    if onboarding.phase == OnboardingPhase.PACKAGE_CREATED:
        steps.append("Complete ERP sync and cloud compliance steps.")
    if not steps:
        steps.append("No immediate action required.")
    return steps
