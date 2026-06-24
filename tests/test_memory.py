from app.memory.store import ProcessStore
from app.tools import service


def test_get_by_idempotency_key(tmp_path):
    store = ProcessStore(tmp_path / "process_state.db")
    service.process_store = store

    first = service.create_onboarding(
        name="Lookup Supplier",
        country="DE",
        vat_id="DE777777777",
        confirmed=True,
    )
    key = first["onboarding"]["idempotency_key"]
    found = store.get_by_idempotency_key(key)

    assert found is not None
    assert found.id == first["onboarding"]["id"]
