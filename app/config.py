"""Settings come from environment variables, never from hardcoded values."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"        # local / dev / staging / prod
    log_level: str = "INFO"
    api_key: str                  # SECRET: no default on purpose
    database_url: str             # contains a password, so treat it as a secret
    redis_url: str                # e.g. redis://redis:6379/0
    cache_ttl_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
