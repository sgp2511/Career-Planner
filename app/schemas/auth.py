"""
Pydantic schemas for authentication requests and responses.
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr = Field(..., description="User's email address", examples=["user@example.com"])
    password: str = Field(
        ..., min_length=6, max_length=128, description="Password (min 6 characters)"
    )
    full_name: str | None = Field(
        None, max_length=255, description="User's full name (optional)"
    )


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class TokenResponse(BaseModel):
    """Response returned after successful login."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")


class UserResponse(BaseModel):
    """Public user information returned by the API."""

    id: int
    email: str
    full_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
