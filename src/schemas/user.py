"""User schemas with password security validation."""

from typing import List, Optional
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, Field
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    first_name: str
    last_name: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating a user with password validation."""
    password: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, password: str) -> str:
        from src.utils.validators import validate_password_strength
        
        result = validate_password_strength(password)
        if not result["valid"]:
            raise ValueError(f"Password validation failed: {', '.join(result['errors'])}")
        
        return password


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: int
    is_verified: bool
    password_changed_at: Optional[datetime] = None
    force_password_change: bool
    last_login: Optional[datetime] = None
    mfa_enabled: Optional[bool]
    
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=8, description="MFA TOTP code or backup code")


class PasswordChange(BaseModel):
    """Schema for password change."""
    current_password: str
    new_password: str
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, password: str) -> str:
        from src.utils.validators import validate_password_strength
        
        result = validate_password_strength(password)
        if not result["valid"]:
            raise ValueError(f"Password validation failed: {', '.join(result['errors'])}")
        
        return password


class PasswordReset(BaseModel):
    """Schema for password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""
    token: str
    new_password: str
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, password: str) -> str:
        from src.utils.validators import validate_password_strength
        
        result = validate_password_strength(password)
        if not result["valid"]:
            raise ValueError(f"Password validation failed: {', '.join(result['errors'])}")
        
        return password


class PasswordStrengthCheck(BaseModel):
    """Schema for password strength checking."""
    password: str


class PasswordStrengthResponse(BaseModel):
    """Schema for password strength response."""
    valid: bool
    strength_score: int
    errors: List[str]
    feedback: List[str]


class Token(BaseModel):
    """Schema for token response with session information."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_verified: bool = Field(default=False, description="Whether MFA was verified")
    requires_mfa: bool = Field(default=False, description="Whether MFA is required for this user")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    device_fingerprint: Optional[str] = Field(None, description="Device fingerprint for security")


class TokenData(BaseModel):
    """Schema for token data."""
    user_id: Optional[int] = None
