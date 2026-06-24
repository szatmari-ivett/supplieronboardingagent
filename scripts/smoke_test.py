import os
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    if os.getenv("SMOKE_USE_ISOLATED_DB", "1") == "1":
        from app.connectors.reset import reset_connector_state
        from app.memory.store import configure_process_store

        smoke_db = root / "data" / "smoke_process_state.db"
        configure_process_store(smoke_db)
        reset_connector_state()

    from app.agent.graph import run_agent

    messages = [
        "Does supplier FreshFarm GmbH already exist? VAT DE123456789",
        "Start onboarding for NewOrganic Ltd, UK, VAT GB987654321",
        "What is the status of onboarding ONB-001?",
    ]

    for message in messages:
        print("---", message)
        result = run_agent(message, session_id="smoke")
        print(result["response"][:300])
        print("tool:", result["metadata"].get("tool"))
        print()


if __name__ == "__main__":
    main()
