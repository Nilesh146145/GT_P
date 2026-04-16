"""
Contributor self-registration (``POST /auth/register/contributor``).
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.auth import AuthUser


def _validate_password(v: str) -> str:
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 characters (bcrypt limit)")
    return v


class ContributorRegisterRequest(BaseModel):
    """Body for ``POST /auth/register/contributor`` (camelCase JSON)."""

    email: EmailStr
    password: str = Field(min_length=12)
    first_name: str = Field(validation_alias="firstName")
    last_name: str = Field(validation_alias="lastName")

    accept_tos: bool = Field(default=False, validation_alias="acceptTos")
    accept_pp: bool = Field(default=False, validation_alias="acceptPp")
    accept_ahp: bool = Field(default=False, validation_alias="acceptAhp")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, v: str) -> str:
        return _validate_password(v)

    @model_validator(mode="after")
    def legal_acceptances_required(self):
        if not all((self.accept_tos, self.accept_pp, self.accept_ahp)):
            raise ValueError("acceptTos, acceptPp, and acceptAhp must all be true to register.")
        return self


class ContributorRegisterResponse(BaseModel):
    user: AuthUser
