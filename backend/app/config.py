from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = ""
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    APP_NAME: str = "LSS ERP"
    DEBUG: bool = False
    API_DOCS_ENABLED: bool = True
    AUTO_CREATE_SCHEMA: bool = True
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    NTS_BUSINESS_STATUS_SERVICE_KEY: str = ""
    NTS_BUSINESS_STATUS_URL: str = "https://api.odcloud.kr/api/nts-businessman/v1/status"
    POSTAL_SERVICE_KEY: str = ""
    POSTAL_API_URL: str = "http://openapi.epost.go.kr/postal/retrieveNewAdressAreaCdSearchAllService/retrieveNewAdressAreaCdSearchAllService/getNewAddressListAreaCdSearchAll"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "LSS ERP"
    SMTP_ADMIN_EMAILS: str = ""

    @property
    def origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def admin_emails(self) -> List[str]:
        return [email.strip() for email in self.SMTP_ADMIN_EMAILS.split(",") if email.strip()]

    @property
    def is_production_like(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod", "staging"}

    def validate_runtime_security(self) -> None:
        issues = []
        if not self.DATABASE_URL:
            issues.append("DATABASE_URL must be configured.")
        if not self.SECRET_KEY:
            issues.append("SECRET_KEY must be configured.")
        if len(self.SECRET_KEY) < 32:
            issues.append("SECRET_KEY must be at least 32 characters.")
        if not self.is_production_like:
            if issues:
                raise RuntimeError("Invalid runtime configuration: " + " ".join(issues))
            return
        if self.API_DOCS_ENABLED:
            issues.append("API_DOCS_ENABLED must be false for production/staging.")
        if self.AUTO_CREATE_SCHEMA:
            issues.append("AUTO_CREATE_SCHEMA must be false for production/staging; use Alembic migrations.")
        if issues:
            raise RuntimeError("Unsafe runtime configuration: " + " ".join(issues))

    class Config:
        env_file = str(ENV_FILE)


settings = Settings()
settings.validate_runtime_security()
