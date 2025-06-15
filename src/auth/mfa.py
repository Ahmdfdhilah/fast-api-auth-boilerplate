"""Multi-Factor Authentication (MFA) implementation with TOTP."""

import secrets
import time
import hmac
import hashlib
import base64
import struct
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from ..repositories.user import UserRepository
from src.repositories.user_mfa import UserMFARepository
from src.auth.jwt import create_access_token

# TOTP Configuration
TOTP_INTERVAL = 30  # 30 seconds
TOTP_DIGITS = 6  # 6-digit codes
TOTP_WINDOW = 2  # Allow codes from 2 intervals before/after


class TOTPManager:
    """Time-based One-Time Password (TOTP) manager."""
    
    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret key."""
        secret = secrets.token_bytes(32)
        return base64.b32encode(secret).decode('utf-8')
    
    @staticmethod
    def generate_qr_code_url(secret: str, email: str, issuer: str = None) -> str:
        """Generate QR code URL for TOTP setup."""
        if issuer is None:
            issuer = settings.PROJECT_NAME
        
        # Format: otpauth://totp/ISSUER:EMAIL?secret=SECRET&issuer=ISSUER
        return (f"otpauth://totp/{issuer}:{email}?"
                f"secret={secret}&issuer={issuer}&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_INTERVAL}")
    
    @staticmethod
    def _get_counter(timestamp: Optional[int] = None) -> int:
        """Get TOTP counter for given timestamp."""
        if timestamp is None:
            timestamp = int(time.time())
        return timestamp // TOTP_INTERVAL
    
    @staticmethod
    def _generate_hotp(secret: str, counter: int) -> str:
        """Generate HOTP code for given counter."""
        # Decode base32 secret
        secret_bytes = base64.b32decode(secret.upper())
        
        # Convert counter to bytes
        counter_bytes = struct.pack('>Q', counter)
        
        # Generate HMAC-SHA1
        hmac_digest = hmac.new(secret_bytes, counter_bytes, hashlib.sha1).digest()
        
        # Dynamic truncation
        offset = hmac_digest[-1] & 0x0f
        truncated = struct.unpack('>I', hmac_digest[offset:offset + 4])[0]
        truncated &= 0x7fffffff
        
        # Generate OTP
        otp = truncated % (10 ** TOTP_DIGITS)
        return str(otp).zfill(TOTP_DIGITS)
    
    @classmethod
    def generate_totp(cls, secret: str, timestamp: Optional[int] = None) -> str:
        """Generate TOTP code for given timestamp."""
        counter = cls._get_counter(timestamp)
        return cls._generate_hotp(secret, counter)
    
    @classmethod
    def verify_totp(cls, secret: str, code: str, timestamp: Optional[int] = None) -> bool:
        """Verify TOTP code with time window tolerance."""
        if timestamp is None:
            timestamp = int(time.time())
        
        current_counter = cls._get_counter(timestamp)
        
        # Check current and nearby time windows
        for i in range(-TOTP_WINDOW, TOTP_WINDOW + 1):
            counter = current_counter + i
            expected_code = cls._generate_hotp(secret, counter)
            if secrets.compare_digest(code, expected_code):
                return True
        
        return False


class MFAService:
    """Multi-Factor Authentication service."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserMFARepository(session)
    
    async def enable_mfa(self, user_id: int) -> Dict[str, Any]:
        """Enable MFA for a user and return setup information."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is already enabled"
            )
        
        # Generate new secret
        mfa_secret = TOTPManager.generate_secret()
        
        # Save secret (temporarily until verified)
        await self.user_repo.update_mfa_secret(user_id, mfa_secret, enabled=False)
        
        # Generate QR code URL
        qr_code_url = TOTPManager.generate_qr_code_url(mfa_secret, user.email)
        
        return {
            "secret": mfa_secret,
            "qr_code_url": qr_code_url,
            "backup_codes": await self._generate_backup_codes(user_id)
        }
    
    async def verify_and_enable_mfa(self, user_id: int, totp_code: str) -> bool:
        """Verify TOTP code and enable MFA."""
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA setup not initiated"
            )
        
        if user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is already enabled"
            )
        
        # Verify TOTP code
        if not TOTPManager.verify_totp(user.mfa_secret, totp_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )
        
        # Enable MFA
        await self.user_repo.update_mfa_secret(user_id, user.mfa_secret, enabled=True)
        return True
    
    async def disable_mfa(self, user_id: int, totp_code: str) -> bool:
        """Disable MFA for a user."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if not user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled"
            )
        
        # Verify TOTP code
        if not TOTPManager.verify_totp(user.mfa_secret, totp_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )
        
        # Disable MFA
        await self.user_repo.update_mfa_secret(user_id, None, enabled=False)
        await self.user_repo.clear_backup_codes(user_id)
        return True
    
    async def verify_mfa_code(self, user_id: int, code: str) -> bool:
        """Verify MFA code (TOTP or backup code)."""
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.mfa_enabled:
            return False
        
        # First try TOTP
        if TOTPManager.verify_totp(user.mfa_secret, code):
            return True
        
        # Then try backup codes
        backup_codes = await self.user_repo.get_backup_codes(user_id)
        for backup_code in backup_codes:
            if not backup_code.used and secrets.compare_digest(backup_code.code, code):
                # Mark backup code as used
                await self.user_repo.use_backup_code(backup_code.id)
                return True
        
        return False
    
    async def _generate_backup_codes(self, user_id: int, count: int = 10) -> list[str]:
        """Generate backup codes for MFA recovery."""
        codes = []
        for _ in range(count):
            code = secrets.token_hex(4).upper()  # 8 character hex codes
            codes.append(code)
        
        # Save to database
        await self.user_repo.save_backup_codes(user_id, codes)
        return codes
    
    async def regenerate_backup_codes(self, user_id: int) -> list[str]:
        """Regenerate backup codes for a user."""
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled"
            )
        
        # Clear existing backup codes
        await self.user_repo.clear_backup_codes(user_id)
        
        # Generate new ones
        return await self._generate_backup_codes(user_id)
    
    async def get_mfa_status(self, user_id: int) -> Dict[str, Any]:
        """Get MFA status for a user."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        backup_codes_count = 0
        if user.mfa_enabled:
            backup_codes = await self.user_repo.get_backup_codes(user_id)
            backup_codes_count = len([code for code in backup_codes if not code.used])
        
        return {
            "mfa_enabled": user.mfa_enabled,
            "backup_codes_remaining": backup_codes_count
        }


class MFAMiddleware:
    """Middleware for enforcing MFA when required."""
    
    @staticmethod
    def require_mfa_verification(user_data: Dict[str, Any]) -> bool:
        """Check if user needs MFA verification."""
        # Check if user has MFA enabled
        if not user_data.get("mfa_enabled", False):
            return False
        
        # Check if current session has MFA verified
        return not user_data.get("mfa_verified", False)
    
    @staticmethod
    def create_mfa_verified_token(user_data: Dict[str, Any]) -> str:
        """Create a new JWT token with MFA verification flag."""
        token_data = {
            "sub": str(user_data["id"]),
            "email": user_data["email"],
            "mfa_verified": True
        }
        return create_access_token(token_data)


# Admin functions for MFA management
class MFAAdminService:
    """Admin functions for MFA management."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
    
    async def force_disable_mfa(self, user_id: int) -> bool:
        """Force disable MFA for a user (admin only)."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if not user.mfa_enabled:
            return False
        
        # Disable MFA without requiring verification
        await self.user_repo.update_mfa_secret(user_id, None, enabled=False)
        await self.user_repo.clear_backup_codes(user_id)
        return True
    
    async def get_mfa_stats(self) -> Dict[str, int]:
        """Get MFA usage statistics."""
        stats = await self.user_repo.get_mfa_stats()
        return {
            "total_users": stats.get("total_users", 0),
            "mfa_enabled_users": stats.get("mfa_enabled_users", 0),
            "mfa_adoption_rate": round(
                (stats.get("mfa_enabled_users", 0) / max(stats.get("total_users", 1), 1)) * 100, 2
            )
        }
