"""Central settings/config engine.

Loads deployment-level configuration from environment variables (see
.env.example at the repo root).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Sham ERP"
    ENVIRONMENT: str = "development"

    COMPANY_NAME: str = "Default Company"
    DEFAULT_CURRENCY: str = "KWD"
    DEFAULT_LOCALE: str = "ar"

    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/sham_erp"
    REDIS_URL: str = "redis://redis:6379/0"

    SECRET_KEY: str = "changeme"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
