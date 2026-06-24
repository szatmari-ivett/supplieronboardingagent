from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "mock"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-haiku-latest"

    fault_erp: bool = False
    fault_procurement: bool = False
    fault_cloud: bool = False

    connector_max_retries: int = 3
    connector_timeout_seconds: float = 5.0
    log_level: str = "INFO"

    database_path: Path = DATA_DIR / "process_state.db"
    checkpoint_path: Path = DATA_DIR / "checkpoints.db"
    suppliers_seed_path: Path = Path(__file__).resolve().parent / "data" / "suppliers_seed.json"


settings = Settings()
