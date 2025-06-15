"""User service with password security features."""

from typing import Optional
from datetime import datetime
from fastapi import HTTPException, status

from src.repositories.user import UserRepository
from src.schemas.user import UserCreate, UserUpdate, UserResponse, PasswordChange
from src.auth.jwt import get_password_hash, verify_password
from src.utils.validators import validate_password_history, validate_password_strength


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user with password validation."""
        # Check if user exists
        existing_user = await self.user_repo.get_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Create user
        user = await self.user_repo.create(user_data, hashed_password)
        
        return UserResponse.model_validate(user)

    async def authenticate_user(self, email: str, password: str) -> Optional[UserResponse]:
        """Authenticate user with account lockout protection."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            return None
        
        # Check if account is locked
        if user.is_locked():
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked due to too many failed login attempts"
            )
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            # Increment failed attempts (this will auto-lock if needed)
            updated_user = await self.user_repo.increment_failed_login_attempts(user.id)
            
            # Check if account is now locked
            if updated_user and updated_user.is_locked():
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account locked due to too many failed login attempts. Try again in {updated_user.lockout_duration_minutes} minutes."
                )
            
            return None
        
        # Reset failed attempts on successful login
        await self.user_repo.reset_failed_login_attempts(user.id)
        
        return UserResponse.model_validate(user)

    async def get_user(self, user_id: int) -> Optional[UserResponse]:
        """Get user by ID."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None
        
        return UserResponse.model_validate(user)

    async def change_password(self, user_id: int, password_data: PasswordChange) -> UserResponse:
        """Change user password with validation."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Verify current password
        if not verify_password(password_data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )

        # Check password history
        if not validate_password_history(password_data.new_password, user.password_history):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reuse any of your last 5 passwords"
            )

        # Hash new password
        new_hashed_password = get_password_hash(password_data.new_password)
        
        # Update password
        updated_user = await self.user_repo.update_password(user_id, new_hashed_password)
        
        return UserResponse.model_validate(updated_user)

    async def check_password_strength(self, password: str) -> dict:
        """Check password strength and provide feedback."""
        result = validate_password_strength(password)
        
        from src.utils.password import get_password_strength_feedback
        feedback = get_password_strength_feedback(password)
        
        return {
            "valid": result["valid"],
            "strength_score": result["strength_score"],
            "errors": result["errors"],
            "feedback": feedback
        }
    
    async def unlock_user_account(self, user_id: int) -> UserResponse:
        """Unlock user account (admin function)."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Unlock account
        await self.user_repo.unlock_account(user_id)
        
        # Get updated user
        updated_user = await self.user_repo.get_by_id(user_id)
        return UserResponse.model_validate(updated_user)
