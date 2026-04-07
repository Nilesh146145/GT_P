"""
Auth Router
───────────
  POST   /auth/login
  POST   /auth/validate
  POST   /auth/register/enterprise
  POST   /auth/register/contributor
  POST   /auth/refresh
  POST   /auth/logout
  POST   /auth/logout-all
  GET    /auth/me
  GET    /auth/session
  GET    /auth/sessions
  DELETE /auth/sessions/{session_id}
  POST   /auth/password/forgot
"""


from typing import Union

from fastapi import APIRouter, Depends, Request

from app.core.security import get_current_user, get_current_user_for_me
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MfaPendingLoginResponse,
    PasswordChangeRequest,
    RefreshRequest,
    SessionListResponse,
    TokenPair,
    ValidateResponse,
)
from app.services import mfa_service
from app.schemas.contributor_auth import ContributorRegisterRequest, ContributorRegisterResponse
from app.schemas.enterprise_auth import EnterpriseRegisterRequest, EnterpriseRegisterResponse
from app.services import auth_service, contributor_auth_service, enterprise_auth_service, password_service
from app.services.reviewer import reviewer_auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Union[LoginResponse, MfaPendingLoginResponse])
async def login(
    payload: LoginRequest,
    request: Request,
) -> Union[LoginResponse, MfaPendingLoginResponse]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await auth_service.login_user(payload, ip_address=ip_address, user_agent=user_agent)


@router.post("/validate", response_model=ValidateResponse)
async def validate(payload: LoginRequest) -> ValidateResponse:
    return await auth_service.validate_credentials(payload)


@router.post("/register/enterprise", response_model=EnterpriseRegisterResponse, status_code=201)
async def register_enterprise(payload: EnterpriseRegisterRequest) -> EnterpriseRegisterResponse:
    return await enterprise_auth_service.register_enterprise(payload)


@router.post("/register/contributor", response_model=ContributorRegisterResponse, status_code=201)
async def register_contributor(payload: ContributorRegisterRequest) -> ContributorRegisterResponse:
    """Create a contributor account (MFA optional; can enable later in settings)."""
    return await contributor_auth_service.register_contributor(payload)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest) -> TokenPair:
    return await auth_service.refresh_session(payload.refresh_token)


@router.post("/logout", response_model=LogoutResponse)
async def logout(payload: RefreshRequest) -> LogoutResponse:
    await auth_service.logout_session(payload.refresh_token)
    return LogoutResponse(success=True)


@router.post("/logout-all", response_model=LogoutResponse)
async def logout_all(current_user: dict = Depends(get_current_user)) -> LogoutResponse:
    await auth_service.logout_all_sessions(current_user["id"])
    return LogoutResponse(success=True)


@router.get("/me", response_model=CurrentUserResponse, response_model_by_alias=True)
async def me(current_user: dict = Depends(get_current_user_for_me)) -> CurrentUserResponse:
    u = dict(current_user)
    auth_pending = u.pop("_auth_token_type", None) == "mfa_pending"
    u.pop("_mfa_flow", None)
    uid = str(u["_id"])
    return CurrentUserResponse(
        id=uid,
        firstName=u.get("first_name", ""),
        lastName=u.get("last_name", ""),
        email=u["email"],
        emailVerified=u.get("email_verified", False),
        phoneVerified=u.get("phone_verified", False),
        role=u.get("role", "contributor"),
        requiresPasswordChange=reviewer_auth_service.reviewer_requires_password_change(u),
        isFirstLogin=bool(u.get("is_first_login", False)),
        mfaEnabled=bool(u.get("mfa_enabled", False)),
        mfaEnrollmentRequired=mfa_service.mfa_enrollment_required(u),
        authPending=auth_pending,
    )


@router.get("/session", response_model=CurrentUserResponse, response_model_by_alias=True)
async def session(current_user: dict = Depends(get_current_user_for_me)) -> CurrentUserResponse:
    return await me(current_user)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(current_user: dict = Depends(get_current_user)) -> SessionListResponse:
    return await auth_service.list_sessions(current_user["id"])


@router.delete("/sessions/{session_id}", response_model=LogoutResponse)
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> LogoutResponse:
    await auth_service.revoke_session_by_id(session_id=session_id, user_id=current_user["id"])
    return LogoutResponse(success=True)


@router.post("/password/change", response_model=LogoutResponse)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
) -> LogoutResponse:
    await password_service.change_password(
        current_user["id"],
        payload.current_password,
        payload.new_password,
    )
    return LogoutResponse(success=True)


@router.post("/password/forgot", response_model=LogoutResponse)
async def forgot_password(payload: ForgotPasswordRequest) -> LogoutResponse:
    await password_service.start_password_reset(payload.email, payload.role)
    return LogoutResponse(success=True)
