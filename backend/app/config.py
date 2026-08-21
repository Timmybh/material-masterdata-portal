from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Material Masterdata Portal"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:12345678@postgres:5432/masterdata"
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_exp_minutes: int = 480
    google_client_id: str = ""
    cors_origins: str = "http://localhost:5173,http://localhost:8088"
    bootstrap_admin_emails: str = ""
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = ""
    masterdata_emails: str = ""
    accounting_emails: str = ""
    dev_auth_enabled: bool = False
    email_notifications_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.local"
    smtp_starttls: bool = True
    frontend_url: str = "http://localhost:5173"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: int = 30
    auto_import_enabled: bool = True
    auto_import_file_path: str = "/data/Danh muc vat tu.xlsx"
    auto_import_hour: int = 19
    auto_import_minute: int = 0
    auto_import_timezone: str = "Asia/Ho_Chi_Minh"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def email_set(self, raw: str) -> set[str]:
        return {x.strip().lower() for x in raw.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
