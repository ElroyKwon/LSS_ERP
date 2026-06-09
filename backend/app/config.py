from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+pg8000://erp_user:erp_password@localhost:5432/lss_erp"
    SECRET_KEY: str = "change-this-secret-key-in-production-at-least-32-chars"
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

    @property
    def origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = str(ENV_FILE)


settings = Settings()
