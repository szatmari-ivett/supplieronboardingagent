from app.observability.guardrails import mask_pii, sanitize_log_payload


def test_mask_pii_redacts_vat_id():
    masked = mask_pii("Check supplier VAT DE123456789")
    assert "DE123456789" not in masked
    assert "DE***6789" in masked


def test_mask_pii_redacts_email():
    masked = mask_pii("Contact buyer@supplier.example for updates")
    assert "buyer@supplier.example" not in masked
    assert "b***@supplier.example" in masked


def test_sanitize_log_payload_masks_string_fields():
    payload = sanitize_log_payload(
        {
            "session_id": "demo-session",
            "message": "VAT GB987654321 for buyer@acme.co.uk",
        }
    )
    assert "GB987654321" not in payload["message"]
    assert "buyer@acme.co.uk" not in payload["message"]
