from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ==========================================
    # APLICACIÓN
    # ==========================================
    app_name: str = Field(
        default="GUARDIAHEXBOT",
        alias="APP_NAME",
    )

    app_env: str = Field(
        default="development",
        alias="APP_ENV",
    )

    app_debug: bool = Field(
        default=True,
        alias="APP_DEBUG",
    )

    app_host: str = Field(
        default="0.0.0.0",
        alias="APP_HOST",
    )

    app_port: int = Field(
        default=8100,
        alias="APP_PORT",
    )

    # ==========================================
    # SEGURIDAD
    # ==========================================
    secret_key: str = Field(
        default="CHANGE_ME",
        alias="SECRET_KEY",
    )

    access_token_expire_minutes: int = Field(
        default=1440,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # ==========================================
    # BASE DE DATOS
    # ==========================================
    database_url: str = Field(
        default=(
            "postgresql+asyncpg://"
            "usuario:password@localhost:5432/guardiahex"
        ),
        alias="DATABASE_URL",
    )

    # ==========================================
    # GUARDIAHEXBOT MASTER
    # ==========================================
    master_bot_token: str = Field(
        default="",
        alias="MASTER_BOT_TOKEN",
    )

    superadmin_telegram_id: int | None = Field(
        default=None,
        alias="SUPERADMIN_TELEGRAM_ID",
    )

    # ==========================================
    # FUENTESDATA
    # ==========================================
    fuentesdata_enabled: bool = Field(
        default=False,
        alias="FUENTESDATA_ENABLED",
    )

    fuentesdata_base_url: str = Field(
        default="",
        alias="FUENTESDATA_BASE_URL",
    )

    fuentesdata_token: str = Field(
        default="",
        alias="FUENTESDATA_TOKEN",
    )

    fuentesdata_timeout: int = Field(
        default=30,
        alias="FUENTESDATA_TIMEOUT",
    )

    # ==========================================
    # GRUPOS GLOBALES
    # ==========================================
    global_history_chat_id: int | None = Field(
        default=None,
        alias="GLOBAL_HISTORY_CHAT_ID",
    )

    global_sales_chat_id: int | None = Field(
        default=None,
        alias="GLOBAL_SALES_CHAT_ID",
    )

    # ==========================================
    # SISTEMA
    # ==========================================
    default_register_credits: int = Field(
        default=5,
        alias="DEFAULT_REGISTER_CREDITS",
    )

    max_founders_per_bot: int = Field(
        default=4,
        alias="MAX_FOUNDERS_PER_BOT",
    )

    # ==========================================
    # TIEMPO REAL
    # ==========================================
    websocket_enabled: bool = Field(
        default=True,
        alias="WEBSOCKET_ENABLED",
    )

    # ==========================================
    # ARCHIVOS
    # ==========================================
    upload_dir: str = Field(
        default="uploads",
        alias="UPLOAD_DIR",
    )

    report_dir: str = Field(
        default="reports",
        alias="REPORT_DIR",
    )

    max_upload_mb: int = Field(
        default=20,
        alias="MAX_UPLOAD_MB",
    )

    # ==========================================
    # ZONA HORARIA
    # ==========================================
    timezone: str = Field(
        default="America/Lima",
        alias="TIMEZONE",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def api_ready(self) -> bool:
        return bool(
            self.fuentesdata_enabled
            and self.fuentesdata_base_url
            and self.fuentesdata_token
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
