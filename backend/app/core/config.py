"""
Centralized application settings loaded from environment variables.
Using pydantic-settings so config is validated at startup instead of
failing deep inside a request handler.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "SecureHire AI"
    ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    # --- Security / JWT ---
    SECRET_KEY: str = "change-me-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+psycopg2://securehire:securehire@localhost:5432/securehire"
    )

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    PREDICTION_CACHE_TTL_SECONDS: int = 3600

    # --- ML ---
    MODEL_DIR: str = "../models"
    MODEL_VERSION: str = "v1.1.0"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
