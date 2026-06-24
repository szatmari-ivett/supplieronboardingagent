import re
from typing import Any

VAT_PATTERN = re.compile(r"\b([A-Z]{2}\d[0-9A-Z]{4,13})\b", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b([^\s@]+)@([^\s@]+\.[^\s@]+)\b")


def mask_pii(text: str) -> str:
    """Redact common supplier PII before writing to logs."""

    def mask_vat(match: re.Match[str]) -> str:
        full = match.group(1).upper()
        prefix, body = full[:2], full[2:]
        if len(body) <= 4:
            return f"{prefix}***"
        return f"{prefix}***{body[-4:]}"

    def mask_email(match: re.Match[str]) -> str:
        user, domain = match.group(1), match.group(2)
        visible = user[0] if user else "*"
        return f"{visible}***@{domain}"

    masked = EMAIL_PATTERN.sub(mask_email, text)
    return VAT_PATTERN.sub(mask_vat, masked)


def sanitize_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            sanitized[key] = mask_pii(value)
        else:
            sanitized[key] = value
    return sanitized
