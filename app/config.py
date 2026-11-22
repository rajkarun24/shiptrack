"""Settings come from environment variables, never from hardcoded values."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the API service."""
    app_env: str = "local"        # local / dev / staging / prod
    log_level: str = "INFO"
    api_key: str                  # SECRET: no default on purpose
    database_url: str             # contains a password, so treat it as a secret
    redis_url: str                # e.g. redis://redis:6379/0
    cache_ttl_seconds: int = 60
    kafka_bootstrap_servers: str  # e.g. kafka:9092
    kafka_topic: str = "parcel-status"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class WorkerSettings(BaseSettings):
    """Settings for the worker. Note: NO api_key. The worker doesn't need it,
    so it never receives it (least privilege)."""
    log_level: str = "INFO"
    database_url: str
    redis_url: str
    kafka_bootstrap_servers: str
    kafka_topic: str = "parcel-status"
    kafka_group_id: str = "shiptrack-worker"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
