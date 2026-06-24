import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import TypeVar

from app.config import settings

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ConnectorError(Exception):
    def __init__(self, system: str, message: str, retryable: bool = True):
        super().__init__(message)
        self.system = system
        self.retryable = retryable


def _run_with_timeout(system: str, operation: Callable[[], T], timeout_seconds: float) -> T:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(operation)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            raise ConnectorError(
                system,
                f"Operation timed out after {timeout_seconds}s",
                retryable=True,
            ) from exc


def with_resilience(system: str, operation: Callable[[], T], idempotency_key: str | None = None) -> T:
    attempts = settings.connector_max_retries
    delay = 0.5
    last_error: ConnectorError | None = None
    timeout_seconds = settings.connector_timeout_seconds

    for attempt in range(1, attempts + 1):
        try:
            logger.info(
                "connector_call system=%s attempt=%s idempotency_key=%s",
                system,
                attempt,
                idempotency_key,
            )
            return _run_with_timeout(system, operation, timeout_seconds)
        except ConnectorError as exc:
            last_error = ConnectorError(system, str(exc), retryable=exc.retryable)
            if not exc.retryable or attempt == attempts:
                break
            logger.warning("connector_retry system=%s attempt=%s error=%s", system, attempt, exc)
        except Exception as exc:  # noqa: BLE001 - surface unknown connector failures as retryable
            last_error = ConnectorError(system, str(exc), retryable=True)
            if attempt == attempts:
                break
            logger.warning("connector_retry system=%s attempt=%s error=%s", system, attempt, exc)

        time.sleep(delay)
        delay *= 2

    assert last_error is not None
    raise last_error
