from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.domain.time_utils import ensure_utc, utc_now


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_EXTERNAL = "waiting_external"
    DONE = "done"
    FAILED = "failed"


class OnboardingPhase(StrEnum):
    INITIATED = "initiated"
    DUPLICATE_CHECK = "duplicate_check"
    PACKAGE_CREATED = "package_created"
    ERP_SYNC = "erp_sync"
    CLOUD_COMPLIANCE = "cloud_compliance"
    ACTIVE = "active"
    FAILED = "failed"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STALE = "stale"


class Supplier(BaseModel):
    id: str | None = None
    name: str
    vat_id: str | None = None
    duns: str | None = None
    country: str
    address: str | None = None


class DuplicateCandidate(BaseModel):
    supplier: Supplier
    score: float
    match_type: str
    reason: str
    recommendation: str


class DuplicateCheckResult(BaseModel):
    query: Supplier
    candidates: list[DuplicateCandidate]
    is_duplicate: bool
    requires_review: bool


class Task(BaseModel):
    id: str
    name: str
    system: str
    status: TaskStatus = TaskStatus.PENDING
    external_ref: str | None = None
    error: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("updated_at", mode="before")
    @classmethod
    def normalize_updated_at(cls, value: object) -> object:
        if isinstance(value, datetime):
            return ensure_utc(value)
        return value


class SystemStatus(BaseModel):
    system: str
    status: str
    phase: OnboardingPhase | None = None
    available: bool = True
    last_sync: datetime = Field(default_factory=utc_now)
    detail: str | None = None

    @field_validator("last_sync", mode="before")
    @classmethod
    def normalize_last_sync(cls, value: object) -> object:
        if isinstance(value, datetime):
            return ensure_utc(value)
        return value


class Onboarding(BaseModel):
    id: str
    supplier: Supplier
    phase: OnboardingPhase = OnboardingPhase.INITIATED
    tasks: list[Task] = Field(default_factory=list)
    idempotency_key: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_datetimes(cls, value: object) -> object:
        if isinstance(value, datetime):
            return ensure_utc(value)
        return value


class AggregatedStatus(BaseModel):
    onboarding_id: str
    supplier_name: str
    canonical_phase: OnboardingPhase
    health: HealthStatus
    systems: list[SystemStatus]
    summary: str
    next_steps: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
