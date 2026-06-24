def test_process_store_isolated_between_tests():
    from app.memory.store import process_store
    from app.tools import service

    first = service.create_onboarding(
        name="Isolated Supplier",
        country="DE",
        vat_id="DE999999999",
        confirmed=True,
    )
    assert first["status"] == "created"
    assert process_store.list_onboardings()
    process_store.clear()
    assert process_store.list_onboardings() == []

    second = service.create_onboarding(
        name="Isolated Supplier",
        country="DE",
        vat_id="DE999999999",
        confirmed=True,
    )
    assert second["status"] == "created"
    assert second["onboarding"]["id"] == "ONB-001"
