from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.user_model import VALID_USER_ROLES


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    """The authenticated identity resolved from a bearer token, used for RBAC
    and company scoping throughout the request."""

    id: str
    username: str
    role: str
    company_id: str
    company_name: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_superadmin(self) -> bool:
        return self.role == "superadmin"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: str
    full_name: str | None = None
    is_active: bool
    company_id: str
    # Resolved from the user's company relationship (User.company_name property).
    company_name: str = ""
    created_at: datetime


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=6, max_length=128)
    role: str = "user"
    full_name: str | None = None

    def normalized_role(self) -> str:
        return self.role if self.role in VALID_USER_ROLES else "user"


class AdminCreate(BaseModel):
    """Superadmin request to create an admin, who gets their own company."""

    username: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=6, max_length=128)
    company_name: str = Field(min_length=1, max_length=255)
    full_name: str | None = None


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: str | None = None
    full_name: str | None = None
    is_active: bool | None = None
