"""MFA-related Pydantic schemas."""

from pydantic import BaseModel, Field
from typing import List, Optional


class MFAEnableRequest(BaseModel):
    """Request to enable MFA."""
    pass


class MFAEnableResponse(BaseModel):
    """Response when enabling MFA."""
    secret: str = Field(..., description="TOTP secret key")
    qr_code_url: str = Field(..., description="QR code URL for authenticator apps")
    backup_codes: List[str] = Field(..., description="Backup recovery codes")


class MFAVerifyRequest(BaseModel):
    """Request to verify MFA setup."""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class MFAVerifyResponse(BaseModel):
    """Response after MFA verification."""
    success: bool = Field(..., description="Whether verification was successful")
    message: str = Field(..., description="Success or error message")


class MFADisableRequest(BaseModel):
    """Request to disable MFA."""
    code: str = Field(..., min_length=6, max_length=8, description="TOTP code or backup code")


class MFACodeRequest(BaseModel):
    """Request with MFA code for login."""
    code: str = Field(..., min_length=6, max_length=8, description="TOTP code or backup code")


class MFAStatusResponse(BaseModel):
    """MFA status response."""
    mfa_enabled: bool = Field(..., description="Whether MFA is enabled")
    backup_codes_remaining: int = Field(..., description="Number of unused backup codes")


class MFAStatsResponse(BaseModel):
    """MFA statistics response (admin only)."""
    total_users: int = Field(..., description="Total number of users")
    mfa_enabled_users: int = Field(..., description="Number of users with MFA enabled")
    mfa_adoption_rate: float = Field(..., description="MFA adoption rate percentage")


class BackupCodesResponse(BaseModel):
    """Backup codes response."""
    backup_codes: List[str] = Field(..., description="New backup recovery codes")


# Login with MFA
class LoginMFARequest(BaseModel):
    """Login request when MFA is required."""
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=8, description="MFA code if required")


class LoginMFAResponse(BaseModel):
    """Login response when MFA is involved."""
    requires_mfa: bool = Field(..., description="Whether MFA verification is required")
    mfa_verified: bool = Field(default=False, description="Whether MFA was verified")
    access_token: Optional[str] = Field(None, description="JWT access token (only if fully authenticated)")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token (only if fully authenticated)")
    token_type: str = Field(default="bearer", description="Token type")
    message: str = Field(..., description="Status message")
