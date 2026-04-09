from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env next to project root (not uvicorn CWD) so OAuth vars load reliably.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DOTENV_PATH = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_DOTENV_PATH) if _DOTENV_PATH.is_file() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "sow_generator"
    # Prevent infinite hangs on Atlas/network issues (critical for Render health checks)
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 10_000
    MONGODB_CONNECT_TIMEOUT_MS: int = 10_000

    # ── JWT / Auth ────────────────────────────────────────────────────────
    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── MFA (TOTP RFC 6238) ───────────────────────────────────────────────
    TOTP_ISSUER: str = "GlimmoraTeam"
    MFA_PENDING_TOKEN_MINUTES: int = 10
    MFA_SETUP_PENDING_MINUTES: int = 15
    TOTP_ENCRYPTION_KEY: Optional[str] = None  # URL-safe base64, 32 bytes raw when decoded; else derived from SECRET_KEY
    TOTP_KEY_ID: str = "app-v1"
    MFA_RECOVERY_CODE_COUNT: int = 10
    MFA_VERIFY_MAX_ATTEMPTS_PER_MINUTE: int = 5
    MFA_RECOVERY_MAX_ATTEMPTS_PER_HOUR: int = 10
    REDIS_URL: Optional[str] = None  # If set, MFA rate limits use Redis (multi-instance)

    # ── NextAuth compatibility ────────────────────────────────────────────
    NEXTAUTH_SECRET: Optional[str] = None

    # ── OAuth (SSO) — set in .env only; never commit real secrets ──────────
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_CLIENT_ID: Optional[str] = None
    MICROSOFT_CLIENT_SECRET: Optional[str] = None
    OAUTH_PUBLIC_BASE_URL: Optional[str] = None
    MICROSOFT_TENANT_ID: str = "common"

    # ── OTP ───────────────────────────────────────────────────────────────
    OTP_EXPIRE_MINUTES: int = 10
    OTP_DRY_RUN: bool = True

    # ── Platform ──────────────────────────────────────────────────────────
    MIN_BUDGET_INR: float = 500_000.0
    MIN_BUDGET_USD: float = 6_000.0
    REVIEWER_API_ENABLED: bool = False
    # When True, mounts /api/v1/billing/* and shows Billing tag in OpenAPI/Swagger.
    BILLING_API_ENABLED: bool = True

    # ── Manual SOW upload flow ────────────────────────────────────────────
    MANUAL_SOW_STORAGE_PATH: str = "uploads/manual_sow"
    MANUAL_SOW_MAX_UPLOAD_BYTES: int = 52_428_800  # 50 MB
    MANUAL_SOW_DUPLICATE_HASH_DAYS: int = 30
    MANUAL_SOW_STALE_GENERATION_DAYS: int = 7
    MANUAL_SOW_RATE_UPLOAD_PER_MINUTE: int = 10
    MANUAL_SOW_RATE_API_PER_MINUTE: int = 60
    MANUAL_SOW_AV_SCAN_ENABLED: bool = False  # set True + wire ClamAV / cloud in production

    @staticmethod
    def _blank_to_none(v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator(
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_CLIENT_SECRET",
        "OAUTH_PUBLIC_BASE_URL",
        "REDIS_URL",
        "TOTP_ENCRYPTION_KEY",
        "NEXTAUTH_SECRET",
        mode="before",
    )
    @classmethod
    def strip_optional_strings(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

    def google_oauth_configured(self) -> bool:
        return bool(self._blank_to_none(self.GOOGLE_CLIENT_ID) and self._blank_to_none(self.GOOGLE_CLIENT_SECRET))

    def microsoft_oauth_configured(self) -> bool:
        return bool(self._blank_to_none(self.MICROSOFT_CLIENT_ID) and self._blank_to_none(self.MICROSOFT_CLIENT_SECRET))


settings = Settings()
