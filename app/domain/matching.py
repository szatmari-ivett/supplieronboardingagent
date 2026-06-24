import json
import logging
import re
from pathlib import Path

from rapidfuzz import fuzz

from app.config import settings
from app.connectors.base import ConnectorError
from app.connectors.erp import ERPConnector
from app.domain.models import DuplicateCandidate, DuplicateCheckResult, Supplier

AUTO_MATCH_THRESHOLD = 95.0
REVIEW_THRESHOLD = 80.0

logger = logging.getLogger(__name__)
_erp = ERPConnector()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[^a-z0-9 ]", " ", value.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_vat(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.upper())


def load_suppliers(seed_path: Path | None = None) -> list[Supplier]:
    path = seed_path or settings.suppliers_seed_path
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [Supplier(**item) for item in payload]


def _recommendation(score: float) -> str:
    if score >= AUTO_MATCH_THRESHOLD:
        return "auto_match"
    if score >= REVIEW_THRESHOLD:
        return "human_review"
    return "new_supplier"


def _score_supplier(query: Supplier, candidate: Supplier) -> DuplicateCandidate | None:
    if query.vat_id and candidate.vat_id and normalize_vat(query.vat_id) == normalize_vat(candidate.vat_id):
        return DuplicateCandidate(
            supplier=candidate,
            score=100.0,
            match_type="exact_vat",
            reason="Exact VAT/tax ID match",
            recommendation="auto_match",
        )

    if query.duns and candidate.duns and query.duns == candidate.duns:
        return DuplicateCandidate(
            supplier=candidate,
            score=100.0,
            match_type="exact_duns",
            reason="Exact DUNS match",
            recommendation="auto_match",
        )

    name_score = fuzz.token_set_ratio(normalize_text(query.name), normalize_text(candidate.name))
    address_score = 0.0
    if query.address and candidate.address:
        address_score = fuzz.token_set_ratio(normalize_text(query.address), normalize_text(candidate.address))

    combined = round(name_score * 0.7 + address_score * 0.3, 2)
    if combined < REVIEW_THRESHOLD:
        return None

    reasons = [f"name similarity {name_score:.1f}%"]
    if address_score:
        reasons.append(f"address similarity {address_score:.1f}%")

    return DuplicateCandidate(
        supplier=candidate,
        score=combined,
        match_type="fuzzy",
        reason=", ".join(reasons),
        recommendation=_recommendation(combined),
    )


def _candidate_key(supplier: Supplier) -> str:
    return normalize_vat(supplier.vat_id) or normalize_text(supplier.name)


def _erp_record_to_supplier(record: dict) -> Supplier:
    return Supplier(
        id=record.get("erp_id"),
        name=record["name"],
        vat_id=record.get("vat_id"),
        country=record.get("country", "DE"),
    )


def _erp_lookup_candidate(query: Supplier) -> DuplicateCandidate | None:
    try:
        record = _erp.lookup_supplier(vat_id=query.vat_id, name=query.name)
    except ConnectorError as exc:
        logger.warning("erp_lookup_unavailable error=%s", exc)
        return None

    if not record:
        return None

    erp_supplier = _erp_record_to_supplier(record)
    scored = _score_supplier(query, erp_supplier)
    if scored:
        return DuplicateCandidate(
            supplier=scored.supplier,
            score=scored.score,
            match_type="erp_lookup",
            reason=f"Found in ERP master data ({scored.reason})",
            recommendation=scored.recommendation,
        )

    return DuplicateCandidate(
        supplier=erp_supplier,
        score=100.0,
        match_type="erp_lookup",
        reason="Found in ERP master data",
        recommendation="auto_match",
    )


def find_duplicate_candidates(query: Supplier, suppliers: list[Supplier] | None = None) -> DuplicateCheckResult:
    catalog = suppliers or load_suppliers()
    candidates: list[DuplicateCandidate] = []
    seen_keys: set[str] = set()

    for supplier in catalog:
        match = _score_supplier(query, supplier)
        if match:
            candidates.append(match)
            seen_keys.add(_candidate_key(match.supplier))

    erp_match = _erp_lookup_candidate(query)
    if erp_match and _candidate_key(erp_match.supplier) not in seen_keys:
        candidates.append(erp_match)

    candidates.sort(key=lambda item: item.score, reverse=True)
    top = candidates[0] if candidates else None
    is_duplicate = bool(top and top.score >= AUTO_MATCH_THRESHOLD)
    requires_review = bool(top and REVIEW_THRESHOLD <= top.score < AUTO_MATCH_THRESHOLD)

    return DuplicateCheckResult(
        query=query,
        candidates=candidates,
        is_duplicate=is_duplicate,
        requires_review=requires_review,
    )
