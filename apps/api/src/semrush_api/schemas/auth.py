"""
Authentication-related Pydantic schemas.

Provides request/response models for:
- Login (email/password authentication)
- Logout
- Current user info (/me endpoint)
"""


from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """
    Login request payload.

    Attributes:
        email: User's email address.
        password: User's password (plain text, will be verified against hash).
    """

    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="User password",
        examples=["secretpassword123"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "secretpassword123",
            }
        }
    )


class LoginResponse(BaseModel):
    """
    Login response with JWT token.

    Follows OAuth 2.0 token response format for compatibility
    with standard OAuth clients.

    Attributes:
        access_token: JWT access token for authenticated requests.
        token_type: Token type (always "bearer").
        expires_in: Token expiration time in seconds.
    """

    access_token: str = Field(
        ...,
        description="JWT access token",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Token expiration time in seconds",
        ge=1,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
            }
        }
    )


class LogoutResponse(BaseModel):
    """
    Logout response.

    Attributes:
        message: Success message.
    """

    message: str = Field(
        default="Successfully logged out",
        description="Logout confirmation message",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Successfully logged out",
            }
        }
    )


class UserResponse(BaseModel):
    """
    Current user information response.

    Used for the /me endpoint to return authenticated user details.
    Excludes sensitive information like password hash.

    Attributes:
        id: User's unique identifier.
        email: User's email address.
        name: User's display name.
        is_active: Whether the account is active.
    """

    id: str = Field(
        ...,
        description="User unique identifier (UUID)",
    )
    email: str = Field(
        ...,
        description="User email address",
    )
    name: str | None = Field(
        None,
        description="User display name",
    )
    is_active: bool = Field(
        ...,
        description="Whether the account is active",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "name": "John Doe",
                "is_active": True,
            }
        }
    )
