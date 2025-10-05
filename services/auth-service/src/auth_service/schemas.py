"""Request and response schemas for auth-service endpoints."""

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, Field, field_validator


USERNAME_PATTERN = r"^[a-z0-9][a-z0-9_-]{2,63}$"


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN)
    email: str = Field(max_length=256)
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=256)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        try:
            email = validate_email(
                value.strip(),
                check_deliverability=False,
                test_environment=True,
            )
        except EmailNotValidError as exc:
            raise ValueError("Invalid email address") from exc

        return email.normalized.lower()


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN)
    password: str

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class AuthUserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    display_name: str | None = None
    is_active: bool


class LoginResponse(BaseModel):
    user_id: str
    username: str
    email: str
    display_name: str | None = None
    access_token: str
    token_type: str
    expires_in: int
