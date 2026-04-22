"""
Authentication router — register, login, and current-user endpoints.

All auth endpoints are prefixed with /api/v1/auth.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.hashing import hash_password, verify_password
from app.auth.jwt import create_access_token, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.

    - Email must be unique.
    - Password is hashed with bcrypt before storage.
    """
    # Check for existing user with the same email
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Create new user with hashed password
    new_user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a JWT access token",
)
def login(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Authenticate with email and password.

    Returns a JWT access token on success.
    The token must be included in the Authorization header as:
        Authorization: Bearer <token>
    """
    # Look up user by email
    user = db.query(User).filter(User.email == request.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Generate JWT — 'sub' claim contains the user ID
    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the profile of the currently authenticated user.

    Requires a valid JWT Bearer token.
    """
    return current_user
