import logging
from typing import Any

from app.config import settings
from app.observability.guardrails import sanitize_log_payload


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def log_event(event: str, **payload: Any) -> None:
    logger = logging.getLogger("supplier_onboarding")
    logger.info("%s %s", event, sanitize_log_payload(payload))
