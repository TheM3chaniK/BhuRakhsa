from functools import lru_cache
from typing import Any
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration settings."""

    # Application Metadata
    APP_NAME: str = "Property Document Verification API"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = (
        "Backend API for evidence-based property document verification, "
        "document processing, validation, and human review."
    )
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API Routing
    API_V1_PREFIX: str = "/api/v1"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Database Configuration
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/property_verification"
    )

    # JWT Authentication Configuration
    JWT_SECRET: str = "dev-insecure-secret-key-change-in-production-min-32-chars-long!"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Initial Super Admin Seed Credentials (for development/bootstrap)
    INITIAL_ADMIN_EMAIL: str = "admin@example.com"
    INITIAL_ADMIN_PASSWORD: str = "Admin@12345678!"

    # File Storage Configuration
    STORAGE_BACKEND: str = "local"
    STORAGE_ROOT: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 25

    # Ollama & DeepSeek OCR Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "deepseek-ocr"
    OLLAMA_TIMEOUT_SECONDS: int = 300
    OCR_MAX_RETRIES: int = 2
    OCR_MAX_CONCURRENCY: int = 1
    MAX_DOCUMENT_PAGES: int = 100
    RUN_OLLAMA_TESTS: bool = False

    # Structured Field Extraction Configuration
    EXTRACTION_MODEL: str = "deepseek-ocr"
    EXTRACTION_TIMEOUT_SECONDS: int = 300
    EXTRACTION_MAX_RETRIES: int = 2
    EXTRACTION_UNCERTAIN_THRESHOLD: float = 0.70

    # Validation & Matching Configuration
    AREA_MATCH_TOLERANCE_PERCENT: float = 1.0
    GIS_AREA_TOLERANCE_PERCENT: float = 2.0

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            if not value.strip():
                return []
            if value.startswith("[") and value.endswith("]"):
                import json
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        elif isinstance(value, (list, tuple, set)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return value

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        """Ensure JWT secret meets security criteria in production environments."""
        if self.ENVIRONMENT == "production":
            if (
                not self.JWT_SECRET
                or len(self.JWT_SECRET) < 32
                or "insecure" in self.JWT_SECRET.lower()
            ):
                raise ValueError(
                    "JWT_SECRET must be a strong secret of at least 32 characters in production."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()


settings = get_settings()
