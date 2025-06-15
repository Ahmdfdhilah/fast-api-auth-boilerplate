"""Application settings and configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, field_validator
from typing import Any, Dict, Optional, List


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    # API settings
    PROJECT_NAME: str
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # CORS
    CORS_ORIGINS: str = "*"
    CORS_HEADERS: str = "*"
    CORS_METHODS: str = "*"

    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"
    DATABASE_URI: Optional[PostgresDsn] = None
    SQL_ECHO: bool = False

    # Database connection pool settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # JWT Settings
    JWT_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Redis (optional)
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[int] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_TTL: int = 3600

    # File handling
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_FILENAME_LENGTH: int = 50

    # Logging
    LOG_DIRECTORY: str = "logs"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    SERVICE_NAME: str

    # Password Security Settings (Step 1)
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_MAX_LENGTH: int = 128
    PASSWORD_HISTORY_COUNT: int = 5
    PASSWORD_MAX_AGE_DAYS: int = 90
    ACCOUNT_LOCKOUT_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_DURATION_MINUTES: int = 15
    
    # Rate Limiting Settings (Step 2)
    RATE_LIMIT_CALLS: int = 100
    RATE_LIMIT_PERIOD: int = 60
    AUTH_RATE_LIMIT_CALLS: int = 5
    AUTH_RATE_LIMIT_PERIOD: int = 300
    
    # Session Management Settings
    MAX_SESSIONS_PER_USER: int = 5
    SESSION_EXPIRE_MINUTES: int = 1440  # 24 hours
    SESSION_CLEANUP_INTERVAL_HOURS: int = 24

    @field_validator("DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], info: Dict[str, Any]) -> Any:
        """Build PostgreSQL connection string from components."""
        if isinstance(v, str):
            return v

        values = info.data
        user = values.get("POSTGRES_USER", "")
        password = values.get("POSTGRES_PASSWORD", "")
        host = values.get("POSTGRES_SERVER", "")
        port = values.get("POSTGRES_PORT", "5432")
        db = values.get("POSTGRES_DB", "")

        auth = f"{user}:{password}" if password else user
        return f"postgresql://{auth}@{host}:{port}/{db}"

    @field_validator("API_V1_STR")
    def ensure_api_prefix_has_slash(cls, v: str) -> str:
        """Ensure API prefix starts with a slash."""
        if not v.startswith("/"):
            return f"/{v}"
        return v

    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        """Convert CORS_ORIGINS string to list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def CORS_METHODS_LIST(self) -> List[str]:
        """Convert CORS_METHODS string to list."""
        if self.CORS_METHODS == "*":
            return ["*"]
        return [method.strip() for method in self.CORS_METHODS.split(",")]

    @property
    def CORS_HEADERS_LIST(self) -> List[str]:
        """Convert CORS_HEADERS string to list."""
        if self.CORS_HEADERS == "*":
            return ["*"]
        return [header.strip() for header in self.CORS_HEADERS.split(",")]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


# Create global settings instance
settings = Settings()
