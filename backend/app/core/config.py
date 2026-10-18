import os
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database Settings
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "jobsentinel"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    # Optional explicit database URL override (e.g., for testing)
    DATABASE_URL: str | None = None

    # Application Settings
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def sync_database_url(self) -> str:
        """Construct a safe SQLAlchemy connection URL using pymysql driver."""
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # Escape username and password to prevent formatting issues with special chars
        escaped_user = quote_plus(self.DB_USER)
        escaped_password = quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+pymysql://{escaped_user}:{escaped_password}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


settings = Settings()
