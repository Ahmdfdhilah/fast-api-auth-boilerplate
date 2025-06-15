"""Authentication service with password security features and session management."""

from datetime import timedelta, datetime
from fastapi import HTTPException, status, Request
from typing import Optional

from src.services.user import UserService
from src.schemas.user import UserLogin, Token, PasswordReset, PasswordResetConfirm
from src.auth.jwt import create_access_token, create_refresh_token
from src.auth.mfa import MFAService
from src.core.config import settings
from src.utils.password import generate_password_reset_token
from src.utils.sessions import device_session_manager


class AuthService:
    def __init__(self, user_service: UserService, session):
        self.user_service = user_service
        self.session = session
        self.mfa_service = MFAService(session)

    async def login(self, login_data: UserLogin, request: Optional[Request] = None) -> Token:
        """Login user and return tokens with security checks and MFA support."""
        user = await self.user_service.authenticate_user(
            login_data.email, 
            login_data.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        # Check if user needs to change password
        if user.force_password_change:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password change required. Please change your password before logging in."
            )

        # Handle MFA verification if enabled
        mfa_verified = True
        requires_mfa = user.mfa_enabled
        
        if user.mfa_enabled:
            if not login_data.mfa_code:
                # User has MFA enabled but didn't provide code
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="MFA code required. Please provide your TOTP code or backup code."
                )
            
            # Verify MFA code
            mfa_verified = await self.mfa_service.verify_mfa_code(user.id, login_data.mfa_code)
            
            if not mfa_verified:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid MFA code"
                )

        # Create token data with MFA verification status
        token_data = {"sub": str(user.id)}
        if user.mfa_enabled:
            token_data["mfa_verified"] = mfa_verified

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data=token_data, 
            expires_delta=access_token_expires
        )
        
        refresh_token = create_refresh_token(data=token_data)

        # Create session with device tracking
        session_info = None
        if request:
            user_agent = request.headers.get("user-agent", "unknown")
            ip_address = self._get_client_ip(request)
            
            session_info = await device_session_manager.create_session(
                user_id=user.id,
                user_agent=user_agent,
                ip_address=ip_address,
                data={
                    "login_time": datetime.utcnow().isoformat(),
                    "mfa_verified": mfa_verified,
                    "requires_mfa": requires_mfa
                }
            )

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            mfa_verified=mfa_verified,
            requires_mfa=requires_mfa,
            session_id=session_info["session_id"] if session_info else None,
            device_fingerprint=session_info["device_fingerprint"] if session_info else None
        )

    async def request_password_reset(self, reset_data: PasswordReset) -> dict:
        """Request password reset token."""
        from src.repositories.user import UserRepository
        from src.core.database import get_db
        
        # Get database session (this would be injected in real implementation)
        async for session in get_db():
            user_repo = UserRepository(session)
            
            user = await user_repo.get_by_email(reset_data.email)
            if not user:
                # Don't reveal if email exists or not
                return {"message": "If the email exists, a reset link has been sent"}

            # Generate reset token
            token = generate_password_reset_token()
            expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
            
            # Save token to database
            await user_repo.create_password_reset_token(user.id, token, expires_at)
            
            # TODO: Send email with reset link (Step 5 implementation)
            # For now, we'll just return the token (remove this in production)
            return {
                "message": "Password reset token generated",
                "token": token  # Remove this in production
            }

    async def confirm_password_reset(self, reset_data: PasswordResetConfirm) -> dict:
        """Confirm password reset with token."""
        from src.repositories.user import UserRepository
        from src.core.database import get_db
        from src.auth.jwt import get_password_hash
        
        # Get database session (this would be injected in real implementation)
        async for session in get_db():
            user_repo = UserRepository(session)
            
            # Get and validate token
            reset_token = await user_repo.get_password_reset_token(reset_data.token)
            if not reset_token or not reset_token.is_valid():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired reset token"
                )

            # Get user
            user = await user_repo.get_by_id(reset_token.user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Check password history
            from src.utils.validators import validate_password_history
            if not validate_password_history(reset_data.new_password, user.password_history):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reuse any of your last 5 passwords"
                )

            # Update password
            new_hashed_password = get_password_hash(reset_data.new_password)
            await user_repo.update_password(user.id, new_hashed_password)
            
            # Mark token as used
            await user_repo.use_password_reset_token(reset_data.token)
            
            return {"message": "Password reset successful"}
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded IP addresses (behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    async def logout(self, session_id: str) -> dict:
        """Logout user and invalidate session."""
        success = await device_session_manager.delete_session(session_id)
        if success:
            return {"message": "Logged out successfully"}
        return {"message": "Session not found or already expired"}
    
    async def logout_all_devices(self, user_id: int) -> dict:
        """Logout user from all devices."""
        deleted_count = await device_session_manager.delete_user_sessions(user_id)
        return {
            "message": f"Logged out from {deleted_count} devices successfully",
            "sessions_terminated": deleted_count
        }
    
    async def revoke_session(self, session_id: str, reason: str = "manual_revocation") -> dict:
        """Revoke a specific session."""
        success = await device_session_manager.revoke_session(session_id, reason)
        if success:
            return {"message": "Session revoked successfully"}
        return {"message": "Session not found or already revoked"}
