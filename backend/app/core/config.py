"""Environment-driven configuration for the RUNWAY backend.

Every tunable lives here so that nothing in the financial engine reads
``os.environ`` directly.  Defaults are chosen so that ``uvicorn app.main:app``
works on a clean checkout with zero external services.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"), env_prefix="RUNWAY_", extra="ignore"
    )

    # ---- application -------------------------------------------------
    app_name: str = "RUNWAY Financial Intelligence OS"
    version: str = "0.9.0"
    env: str = Field(default="demo", description="demo | development | production")
    debug: bool = True

    # ---- persistence ---------------------------------------------------
    # SQLite by default so the project runs with no external service.
    # Point this at postgresql+psycopg://... to use PostgreSQL instead; the
    # ORM models are written to be portable across both.
    database_url: str = f"sqlite:///{DATA_DIR / 'runway.db'}"
    sql_echo: bool = False

    # ---- security ------------------------------------------------------
    secret_key: str = "dev-only-insecure-key-change-me-in-production-0001"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 12 * 60
    pbkdf2_iterations: int = 240_000
    rate_limit_per_minute: int = 240
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ---- financial policy defaults -------------------------------------
    default_safety_buffer_paise: int = 300_000_00     # Rs 3,00,000
    forecast_horizon_weeks: int = 13
    monte_carlo_paths: int = 4000
    monte_carlo_seed: int = 20260101
    var_confidence: float = 0.95

    # ---- AI copilot ------------------------------------------------------
    # When no key is present the copilot falls back to a deterministic
    # natural-language renderer. It never invents numbers either way.
    anthropic_api_key: str | None = None
    copilot_model: str = "claude-opus-5"
    copilot_max_tokens: int = 1400

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
