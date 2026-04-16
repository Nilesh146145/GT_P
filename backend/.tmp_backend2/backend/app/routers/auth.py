"""
Auth Router — aligned with deployed OpenAPI grouping.

**Authentication** (Swagger): login, validate, register/enterprise, register/contributor,
refresh, logout, password/forgot, then protected logout-all, me, session, sessions, revoke.

Legacy ``/register``, form login, and password reset/change stay **callable** but are **hidden** from OpenAPI so Swagger matches production (Authentication + MFA only).

MFA: ``/auth/mfa/*`` (tag **MFA**).
"""

from typing import Union

from fastapi import APIRouter, Depends, Form, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import get_current_user
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MfaRequiredLoginResponse,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    RefreshRequest,
    SessionListResponse,
    TokenPair,
    ValidateResponse,
)
from app.schemas.common import BaseResponse
from app.schemas.contributor_auth import ContributorRegisterRequest, ContributorRegisterResponse
from app.schemas.enterprise_auth import EnterpriseRegisterRequest, EnterpriseRegisterResponse
from app.services import auth_service, contributor_auth_service, enterprise_auth_service, password_service

_TAG = "Authentication"
_TAG_EXT = "Authentication — extended"

# No default tags on this router: a parent ``tags=`` would be merged onto *included* MFA routes too,
# which makes ``/auth/mfa/*`` appear under "Authentication" in Swagger. Tag each route explicitly instead.
router = APIRouter(prefix="/auth")


# ── Public (no Bearer) — order matches common production Swagger layout ───────


@router.post(
    "/login",
    response_model=Union[LoginResponse, MfaRequiredLoginResponse],
    responses={200: {"description": "Tokens, or MFA required (no JWT yet)"}},
    tags=[_TAG],
)
async def login(
    request: Request,
    payload: LoginRequest,
) -> Union[LoginResponse, MfaRequiredLoginResponse]:
    """Sign in with JSON (email + password). If MFA is on, use ``/auth/mfa/verify`` or ``/auth/mfa/recovery``."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await auth_service.login_user(
        payload,
        ip_address=ip_address,
        user_agent=user_agent,
        remember_me=payload.remember_me,
    )


@router.post("/validate", response_model=ValidateResponse, tags=[_TAG])
async def validate(payload: LoginRequest) -> ValidateResponse:
    return await auth_service.validate_credentials(payload)


@router.post(
    "/register/enterprise",
    response_model=EnterpriseRegisterResponse,
    status_code=201,
    tags=[_TAG],
)
async def register_enterprise(payload: EnterpriseRegisterRequest) -> EnterpriseRegisterResponse:
    """Enterprise admin registration (creates enterprise profile + admin user)."""
    return await enterprise_auth_service.register_enterprise(payload)


@router.post(
    "/register/contributor",
    response_model=ContributorRegisterResponse,
    status_code=201,
    tags=[_TAG],
)
async def register_contributor(payload: ContributorRegisterRequest) -> ContributorRegisterResponse:
    """Contributor self-registration (individual account, no enterprise profile)."""
    return await contributor_auth_service.register_contributor(payload)


@router.post("/refresh", response_model=TokenPair, tags=[_TAG])
async def refresh(payload: RefreshRequest) -> TokenPair:
    return await auth_service.refresh_session(payload.refresh_token)


@router.post("/logout", response_model=LogoutResponse, tags=[_TAG])
async def logout(payload: RefreshRequest) -> LogoutResponse:
    await auth_service.logout_session(payload.refresh_token)
    return LogoutResponse(success=True)


@router.post("/password/forgot", response_model=LogoutResponse, tags=[_TAG])
async def forgot_password(payload: ForgotPasswordRequest) -> LogoutResponse:
    await password_service.start_password_reset(payload.email, payload.role)
    return LogoutResponse(success=True)


# ── Protected (Bearer) ───────────────────────────────────────────────────────


@router.post("/logout-all", response_model=LogoutResponse, tags=[_TAG])
async def logout_all(current_user: dict = Depends(get_current_user)) -> LogoutResponse:
    await auth_service.logout_all_sessions(current_user["id"])
    return LogoutResponse(success=True)


@router.get("/me", response_model=BaseResponse, tags=[_TAG])
async def me(current_user: dict = Depends(get_current_user)) -> BaseResponse:
    current_user["id"] = str(current_user["_id"])
    return BaseResponse(
        message="OK",
        data=auth_service.current_user_public_dict(current_user),
    )


@router.get("/session", response_model=BaseResponse, tags=[_TAG])
async def session(current_user: dict = Depends(get_current_user)) -> BaseResponse:
    current_user["id"] = str(current_user["_id"])
    return BaseResponse(
        message="OK",
        data=auth_service.current_user_public_dict(current_user),
    )


@router.get("/sessions", response_model=SessionListResponse, tags=[_TAG])
async def list_sessions(current_user: dict = Depends(get_current_user)) -> SessionListResponse:
    return await auth_service.list_sessions(current_user["id"])


@router.delete("/sessions/{session_id}", response_model=LogoutResponse, tags=[_TAG])
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> LogoutResponse:
    await auth_service.revoke_session_by_id(session_id=session_id, user_id=current_user["id"])
    return LogoutResponse(success=True)


@router.post(
    "/password/change",
    response_model=LogoutResponse,
    tags=[_TAG],
    summary="Change password (authenticated)",
)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
) -> LogoutResponse:
    """Replace password while logged in (e.g. reviewer replacing admin-issued temporary password)."""
    await password_service.change_password(
        current_user["id"],
        payload.current_password,
        payload.new_password,
    )
    return LogoutResponse(success=True)


# ── Extended / legacy (separate Swagger group) ────────────────────────────────


@router.post(
    "/register",
    response_model=BaseResponse,
    status_code=201,
    tags=[_TAG_EXT],
    include_in_schema=False,
    summary="Register enterprise (legacy alias)",
)
async def register_legacy(payload: EnterpriseRegisterRequest) -> BaseResponse:
    """Same as ``POST /auth/register/enterprise``; hidden from OpenAPI (use /register/enterprise)."""
    result = await enterprise_auth_service.register_enterprise(payload)
    return BaseResponse(
        success=True,
        message="Registration successful.",
        data={
            "user": result.user.model_dump(by_alias=True),
            "enterprise_profile_id": result.enterprise_profile_id,
        },
    )


@router.post(
    "/login/form",
    response_model=Union[LoginResponse, MfaRequiredLoginResponse],
    responses={200: {"description": "Tokens, or MFA required (no JWT yet)"}},
    tags=[_TAG_EXT],
    include_in_schema=False,
    summary="Login (OAuth2 form)",
)
async def login_form(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    remember_me: bool = Form(False),
) -> Union[LoginResponse, MfaRequiredLoginResponse]:
    """OAuth2 form: username = email. For Swagger OAuth2 password flow compatibility."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    body = LoginRequest(
        email=form_data.username,
        password=form_data.password,
        remember_me=remember_me,
    )
    return await auth_service.login_user(
        body,
        ip_address=ip_address,
        user_agent=user_agent,
        remember_me=remember_me,
    )


@router.post(
    "/password/reset",
    response_model=LogoutResponse,
    tags=[_TAG_EXT],
    include_in_schema=False,
    summary="Complete password reset (token)",
)
async def reset_password_confirm(payload: PasswordResetConfirmRequest) -> LogoutResponse:
    await password_service.complete_password_reset(payload.token, payload.new_password)
    return LogoutResponse(success=True)


from app.routers.auth_mfa import router as auth_mfa_router

router.include_router(auth_mfa_router)
