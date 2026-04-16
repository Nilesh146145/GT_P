from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# Load repo-root `.env` when uvicorn cwd is `backend/` (later `backend/.env` overrides if present).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILES = (
    str(_BACKEND_ROOT.parent / ".env"),
    str(_BACKEND_ROOT / ".env"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    # ── Database ──────────────────────────────────────────────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "sow_generator"

    # ── JWT / Auth ────────────────────────────────────────────────────────
    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    # Optional override (common in shared .env templates)
    JWT_ALGORITHM: Optional[str] = None
    # FSD §3.4 — access token 8h absolute
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # When "Remember this device" is false — shorter refresh (session-oriented)
    REFRESH_TOKEN_EXPIRE_DAYS_SHORT: int = 1

    # FSD §3.2.2 / §3.3.4 — lockouts
    AUTH_PASSWORD_FAILS_BEFORE_LOCKOUT: int = 5
    AUTH_TOTP_FAILS_BEFORE_LOCKOUT: int = 3
    AUTH_LOCKOUT_MINUTES: int = 15
    MAX_CONCURRENT_SESSIONS: int = 3
    MFA_RECOVERY_CODE_COUNT: int = 8

    # ── TOTP (MFA) ───────────────────────────────────────────────────────
    TOTP_ISSUER: str = "GlimmoraTeam"
    # How long a pending MFA setup (``mfa_temp_secret``) remains valid, in seconds
    OTP_EXPIRE_SECONDS: int = 300
    # RFC 6238 interval (seconds); pyotp default is 30
    TOTP_INTERVAL_SECONDS: int = 30

    # ── NextAuth compatibility ────────────────────────────────────────────
    # NextAuth v5 signs its own JWT with NEXTAUTH_SECRET.
    # Set this to the same value as NEXTAUTH_SECRET in your Next.js .env
    # so that the /auth/validate endpoint can be called by NextAuth's
    # credentials authorize() callback and receive a structured error.
    NEXTAUTH_SECRET: Optional[str] = None

    # ── OAuth (SSO) ───────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_CLIENT_ID: Optional[str] = None
    MICROSOFT_CLIENT_SECRET: Optional[str] = None

    # ── OTP (non-TOTP, e.g. SMS/email codes) ─────────────────────────────
    OTP_EXPIRE_MINUTES: int = 10
    # Set to True in production to use a real SMS/email gateway
    OTP_DRY_RUN: bool = True

    # ── Platform ──────────────────────────────────────────────────────────
    MIN_BUDGET_INR: float = 500_000.0
    MIN_BUDGET_USD: float = 6_000.0
    # Comma-separated emails that may call ``POST /users`` etc. (same as ``PLATFORM_ADMIN_EMAILS`` in ``.env``).
    PLATFORM_ADMIN_EMAILS: Optional[str] = None
    # Expose ``/api/v1/reviewer/*``. Set False to disable reviewer routes (e.g. maintenance).
    REVIEWER_API_ENABLED: bool = True

    @property
    def signing_algorithm(self) -> str:
        """Algorithm for JWT encode/decode (``JWT_ALGORITHM`` overrides ``ALGORITHM``)."""
        return self.JWT_ALGORITHM if self.JWT_ALGORITHM is not None else self.ALGORITHM


settings = Settings()
