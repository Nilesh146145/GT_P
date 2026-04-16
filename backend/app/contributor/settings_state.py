"""In-memory contributor state for demo; replace with persistence."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.contributor.schemas.settings import AccountSummary, NotificationPreferences


@dataclass
class ContributorState:
    account_summary: AccountSummary = field(
        default_factory=lambda: AccountSummary(
            display_name="Contributor",
            email="contributor@example.com",
            phone=None,
        )
    )
    notification_preferences: NotificationPreferences = field(
        default_factory=NotificationPreferences
    )
    language: str = "en"
    timezone: str = "UTC"
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    two_factor_enabled: bool = False
    # Demo-only: replace with password hash verification
    _password_plain_demo: str = "changeme"
    pending_totp_secret: str | None = None
    totp_secret: str | None = None


state = ContributorState()
