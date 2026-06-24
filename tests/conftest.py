import pytest

from app.config import settings
from app.connectors.reset import reset_connector_state
from app.memory import store as memory_store


@pytest.fixture(autouse=True)
def isolated_app_state(tmp_path, monkeypatch):
    db_path = tmp_path / "process_state.db"
    checkpoint_path = tmp_path / "checkpoints.db"
    monkeypatch.setattr(settings, "database_path", db_path)
    monkeypatch.setattr(settings, "checkpoint_path", checkpoint_path)

    memory_store.configure_process_store(db_path)

    from app.agent.graph import reset_agent_graph

    reset_agent_graph()

    monkeypatch.setattr(settings, "fault_erp", False)
    monkeypatch.setattr(settings, "fault_procurement", False)
    monkeypatch.setattr(settings, "fault_cloud", False)

    reset_connector_state()
    yield
    reset_agent_graph()
    reset_connector_state()
