"""Application configuration via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Privacy & DPA Analyzer"
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'dpa_analyzer.db'}"

    uploads_dir: Path = BASE_DIR / "data" / "uploads"
    reports_dir: Path = BASE_DIR / "data" / "reports"
    matrices_dir: Path = BASE_DIR / "data" / "matrices"

    # Anthropic API — can be set via env var or per-request header
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-20250514"

    # Upload limits
    max_file_size_mb: int = 50
    allowed_extensions: set[str] = {".docx", ".pdf"}

    model_config = {"env_prefix": "DPA_", "env_file": ".env"}


settings = Settings()
