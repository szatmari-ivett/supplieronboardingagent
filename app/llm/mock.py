import re
from typing import Any

from app.llm.base import LLMProvider

VAT_LABELED_PATTERN = re.compile(
    r"\bVAT\s*[:\s#]?\s*([A-Z]{2}[0-9A-Z]{5,14})\b",
    re.IGNORECASE,
)
VAT_STANDALONE_PATTERN = re.compile(
    r"\b([A-Z]{2}\d[0-9A-Z]{5,13})\b",
    re.IGNORECASE,
)
ONB_PATTERN = re.compile(r"\b(ONB-\d{3,})\b", re.IGNORECASE)
NAME_STOP_PATTERN = re.compile(
    r"\b(already exist(s)?|exist(s)?|duplicate|check)\b|[?.!]$",
    re.IGNORECASE,
)


class MockLLM(LLMProvider):
    def plan(self, message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        text = message.strip()
        lower = text.lower()
        slots = self._extract_slots(text)

        if any(word in lower for word in ["status", "where", "progress"]):
            return {
                "intent": "aggregate_status",
                "tool": "aggregate_status",
                "arguments": {"onboarding_id": slots.get("onboarding_id", "ONB-001")},
                "requires_confirmation": False,
            }

        if any(word in lower for word in ["start onboarding", "create onboarding", "new supplier"]):
            return {
                "intent": "create_onboarding",
                "tool": "create_onboarding",
                "arguments": {
                    "name": slots.get("name", "NewOrganic Ltd"),
                    "country": slots.get("country", "GB"),
                    "vat_id": slots.get("vat_id"),
                    "address": slots.get("address"),
                    "confirmed": "confirm" in lower or "yes" in lower,
                },
                "requires_confirmation": False,
            }

        if any(word in lower for word in ["duplicate", "already exist", "exists", "check supplier"]):
            return {
                "intent": "duplicate_check",
                "tool": "duplicate_check",
                "arguments": {
                    "name": slots.get("name", self._fallback_name(text)),
                    "vat_id": slots.get("vat_id"),
                    "country": slots.get("country", "DE"),
                    "address": slots.get("address"),
                },
                "requires_confirmation": False,
            }

        return self._help_plan(text)

    def _help_plan(self, text: str) -> dict[str, Any]:
        return {
            "intent": "help",
            "tool": None,
            "arguments": {},
            "requires_confirmation": False,
            "help_text": self._help_text(text),
        }

    def _help_text(self, text: str) -> str:
        lower = text.lower()
        greetings = ("hi", "hello", "hey", "good morning", "good afternoon", "help me", "can you help")
        if any(word in lower for word in greetings):
            return (
                "Hello! I can help with supplier onboarding:\n"
                "- Check whether a supplier already exists\n"
                "- Start a new onboarding package across procurement, ERP, and cloud\n"
                "- Show the status of an existing onboarding\n\n"
                "Share a supplier name, VAT ID, or onboarding ID (for example ONB-001), "
                "or use one of the quick actions below."
            )
        return (
            "I can check duplicate suppliers, start onboarding packages, or provide onboarding status. "
            "Try: 'Does FreshFarm GmbH already exist? VAT DE123456789' or "
            "'Start onboarding for NewOrganic Ltd, UK, VAT GB987654321'."
        )

    def _extract_slots(self, text: str) -> dict[str, Any]:
        slots: dict[str, Any] = {}
        vat = self._extract_vat_id(text)
        if vat:
            slots["vat_id"] = vat
        onb = ONB_PATTERN.search(text)
        if onb:
            slots["onboarding_id"] = onb.group(1).upper()

        country_match = re.search(r"\b(DE|GB|UK|SE|IT|NL|CH|FR|AT)\b", text, re.IGNORECASE)
        if country_match:
            slots["country"] = country_match.group(1).upper().replace("UK", "GB")

        name = self._extract_supplier_name(text)
        if name:
            slots["name"] = name

        address_match = re.search(r"address[: ]+(.+)$", text, re.IGNORECASE)
        if address_match:
            slots["address"] = address_match.group(1).strip()
        return slots

    def _extract_vat_id(self, text: str) -> str | None:
        labeled = VAT_LABELED_PATTERN.search(text)
        if labeled:
            return labeled.group(1).upper()

        for match in VAT_STANDALONE_PATTERN.finditer(text):
            candidate = match.group(1).upper()
            if candidate.isalpha():
                continue
            return candidate
        return None

    def _extract_supplier_name(self, text: str) -> str | None:
        lower = text.lower()
        for marker in ["for ", "supplier "]:
            if marker not in lower:
                continue
            fragment = text.split(marker, 1)[-1]
            fragment = fragment.split(",")[0]
            fragment = re.split(r"\bVAT\b", fragment, flags=re.IGNORECASE)[0]
            fragment = NAME_STOP_PATTERN.sub("", fragment).strip(" ,?")
            if fragment:
                return fragment
        return None

    def _fallback_name(self, text: str) -> str:
        cleaned = VAT_LABELED_PATTERN.sub("", text)
        cleaned = VAT_STANDALONE_PATTERN.sub("", cleaned)
        cleaned = cleaned.replace("?", "").strip()
        return cleaned or "Unknown Supplier"
