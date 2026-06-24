import sqlite3
from pathlib import Path

from app.config import settings
from app.domain.models import Onboarding, OnboardingPhase, Supplier, Task, TaskStatus
from app.domain.time_utils import utc_now


class ProcessStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS onboardings (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(onboardings)")}
            if "idempotency_key" not in columns:
                conn.execute("ALTER TABLE onboardings ADD COLUMN idempotency_key TEXT")
                rows = conn.execute("SELECT id, payload FROM onboardings").fetchall()
                for row in rows:
                    onboarding = Onboarding.model_validate_json(row["payload"])
                    conn.execute(
                        "UPDATE onboardings SET idempotency_key = ? WHERE id = ?",
                        (onboarding.idempotency_key, row["id"]),
                    )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_onboardings_idempotency
                ON onboardings(idempotency_key)
                """
            )

    def save_onboarding(self, onboarding: Onboarding) -> Onboarding:
        onboarding.updated_at = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO onboardings (id, idempotency_key, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    idempotency_key=excluded.idempotency_key,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    onboarding.id,
                    onboarding.idempotency_key,
                    onboarding.model_dump_json(),
                    onboarding.updated_at.isoformat(),
                ),
            )
        return onboarding

    def get_onboarding(self, onboarding_id: str) -> Onboarding | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM onboardings WHERE id = ?", (onboarding_id,)).fetchone()
        if not row:
            return None
        return Onboarding.model_validate_json(row["payload"])

    def get_by_idempotency_key(self, idempotency_key: str) -> Onboarding | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM onboardings WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        if not row:
            return None
        return Onboarding.model_validate_json(row["payload"])

    def list_onboardings(self) -> list[Onboarding]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM onboardings ORDER BY updated_at DESC").fetchall()
        return [Onboarding.model_validate_json(row["payload"]) for row in rows]

    def next_onboarding_id(self) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM onboardings").fetchone()
        count = int(row["total"]) + 1 if row else 1
        return f"ONB-{count:03d}"

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM onboardings")


process_store = ProcessStore()


def configure_process_store(db_path: Path | None = None) -> ProcessStore:
    global process_store
    process_store = ProcessStore(db_path)
    try:
        from app.tools import service as service_module

        service_module.process_store = process_store
    except ImportError:
        pass
    return process_store


def build_initial_tasks() -> list[Task]:
    return [
        Task(id="task-dup", name="Duplicate check", system="agent", status=TaskStatus.DONE),
        Task(id="task-proc", name="Create procurement package", system="procurement", status=TaskStatus.PENDING),
        Task(id="task-erp", name="Sync supplier to ERP", system="erp", status=TaskStatus.PENDING),
        Task(id="task-cloud", name="Trigger cloud compliance", system="cloud", status=TaskStatus.PENDING),
    ]


def create_onboarding_record(supplier: Supplier, idempotency_key: str) -> Onboarding:
    onboarding = Onboarding(
        id=process_store.next_onboarding_id(),
        supplier=supplier,
        phase=OnboardingPhase.INITIATED,
        tasks=build_initial_tasks(),
        idempotency_key=idempotency_key,
    )
    return process_store.save_onboarding(onboarding)
