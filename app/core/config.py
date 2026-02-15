from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "AddSy API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/v1"

    # Database (required)
    DATABASE_URL: str

    # JWT (required)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90

    # OTP
    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 5
    OTP_RATE_LIMIT_SECONDS: int = 60

    # Mobizon SMS (required)
    MOBIZON_API_KEY: str
    MOBIZON_API_URL: str = "https://api.mobizon.kz/service"

    # Platform
    PLATFORM_COMMISSION_PERCENT: int = 10
    WORK_REVIEW_PERIOD_HOURS: int = 24

    # Upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB

    # CORS
    ALLOWED_ORIGINS: str = "*"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def cors_origins(self) -> list[str]:
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
