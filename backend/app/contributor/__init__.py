"""Contributor-facing APIs — same JWT / MFA / OAuth stack as the rest of the platform (see /api/v1/auth/*)."""

from app.contributor.routers import router

__all__ = ["router"]
