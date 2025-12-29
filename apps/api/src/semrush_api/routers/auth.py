"""
Authentication endpoints.

Provides endpoints for:
- POST /auth/register - create new user account
- POST /auth/login - authenticate with email/password, receive JWT
- POST /auth/logout - acknowledge logout (stateless)
- GET /me - retrieve current authenticated user info
"""

from fastapi import APIRouter, HTTPException, status
from semrush_core import get_settings
from semrush_core.models import User
from semrush_core.security.jwt import create_access_token
from semrush_core.security.password import hash_password, verify_password
from sqlalchemy import select

from semrush_api.deps import CurrentUser, DbSession
from semrush_api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)

router = APIRouter()


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email and password.",
    responses={
        409: {
            "description": "Email already registered",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Email already registered",
                    }
                }
            },
        },
        422: {
            "description": "Validation error (invalid email or password too short)",
        },
    },
)
async def register(
    registration: RegisterRequest,
    db: DbSession,
) -> RegisterResponse:
    """
    Register a new user account.

    Creates a new user with the provided email, password, and optional name.
    Password is hashed using bcrypt before storage.

    Args:
        registration: Registration request with email, password, and optional name.
        db: Database session.

    Returns:
        RegisterResponse with created user information.

    Raises:
        HTTPException: 409 if email is already registered.
        HTTPException: 422 if validation fails (invalid email or password too short).
    """
    # Check if email is already registered
    result = await db.execute(select(User).where(User.email == registration.email))
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash the password
    password_hash = hash_password(registration.password)

    # Create the new user
    new_user = User(
        email=registration.email,
        password_hash=password_hash,
        name=registration.name,
        is_active=True,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return RegisterResponse(
        id=str(new_user.id),
        email=new_user.email,
        name=new_user.name,
        is_active=new_user.is_active,
    )


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user",
    description="Authenticate with email and password. Returns JWT access token on success.",
    responses={
        401: {
            "description": "Invalid credentials or inactive account",
            "content": {
                "application/json": {
                    "example": {
                        "error": "unauthorized",
                        "message": "Invalid email or password",
                    }
                }
            },
        },
        422: {
            "description": "Validation error",
        },
    },
)
async def login(
    credentials: LoginRequest,
    db: DbSession,
) -> LoginResponse:
    """
    Authenticate user with email and password.

    Validates credentials against the database and returns a JWT
    access token if successful.

    Args:
        credentials: Login request with email and password.
        db: Database session.

    Returns:
        LoginResponse with access token.

    Raises:
        HTTPException: 401 if credentials are invalid or account is inactive.
    """
    settings = get_settings()

    # Look up user by email
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    # Check if user exists
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(
        subject=str(user.id),
        scopes=["user"],
    )

    # Calculate expiration in seconds
    expires_in = settings.jwt_access_token_expire_minutes * 60

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post(
    "/auth/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    description="Acknowledge logout. Since JWT is stateless, this is informational.",
    responses={
        401: {
            "description": "Not authenticated",
        },
    },
)
async def logout(
    current_user: CurrentUser,
) -> LogoutResponse:
    """
    Logout the current user.

    Since JWTs are stateless, this endpoint simply acknowledges
    the logout request. The client should discard the token.

    For true token invalidation, implement a token blacklist
    (stored in Redis) in future iterations.

    Args:
        current_user: Current authenticated user (from JWT).

    Returns:
        LogoutResponse with success message.
    """
    # In a stateful implementation, we would:
    # 1. Add the token's jti to a blacklist in Redis
    # 2. Set TTL to match token expiration

    return LogoutResponse(message="Successfully logged out")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Retrieve information about the currently authenticated user.",
    responses={
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "User not found",
        },
    },
)
async def get_current_user_info(
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    """
    Get information about the current authenticated user.

    Retrieves the user from the database based on the JWT token's
    subject claim.

    Args:
        current_user: Current authenticated user data from JWT.
        db: Database session.

    Returns:
        UserResponse with user information (excluding password hash).

    Raises:
        HTTPException: 404 if user no longer exists in database.
    """
    # Look up user in database to get current info
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        is_active=user.is_active,
    )
