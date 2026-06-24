from app.domain.matching import find_duplicate_candidates
from app.domain.models import Supplier


def test_exact_vat_match():
    query = Supplier(name="FreshFarm GmbH", vat_id="DE123456789", country="DE")
    result = find_duplicate_candidates(query)
    assert result.is_duplicate is True
    assert result.candidates[0].score == 100.0


def test_fuzzy_name_match_requires_review():
    query = Supplier(name="Fresh Farm", vat_id="DE000000000", country="DE", address="Berliner Str 12 Munich")
    result = find_duplicate_candidates(query)
    assert result.requires_review or result.is_duplicate
    assert result.candidates


def test_no_match_for_new_supplier():
    query = Supplier(name="Totally Unique Supplier", vat_id="GB000000000", country="GB")
    result = find_duplicate_candidates(query)
    assert result.is_duplicate is False
    assert result.requires_review is False


def test_erp_lookup_detects_existing_supplier():
    from app.connectors.erp import ERPConnector

    connector = ERPConnector()
    supplier = Supplier(name="ERP Only Supplier", vat_id="DE888888888", country="DE")
    connector.create_supplier(supplier, "erp-dup-key")

    query = Supplier(name="ERP Only Supplier", vat_id="DE888888888", country="DE")
    result = find_duplicate_candidates(query)
    assert result.is_duplicate is True
    assert any(candidate.match_type == "erp_lookup" for candidate in result.candidates)
