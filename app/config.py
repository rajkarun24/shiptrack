"""Settings come from environment variables, never from hardcoded values."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"        # local / dev / staging / prod
    log_level: str = "INFO"
    api_key: str                  # SECRET: no default on purpose, app won't start without it

    # Reads a local .env file if present; real environment variables win.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
