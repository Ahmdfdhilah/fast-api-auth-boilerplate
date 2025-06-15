"""Authentication endpoints with password security features and session management."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from src.core.database import get_db
from src.repositories.user import UserRepository
from src.services.user import UserService
from src.services.auth import AuthService
from src.schemas.user import (
    UserLogin, UserCreate, UserResponse, Token, PasswordChange,
    PasswordReset, PasswordResetConfirm, PasswordStrengthCheck, PasswordStrengthResponse
)
from src.schemas.common import StatusMessage, SuccessResponse
from src.auth.permissions import get_current_active_user
from src.utils.sessions import device_session_manager

router = APIRouter()


async def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    """Get auth service dependency."""
    user_repo = UserRepository(session)
    user_service = UserService(user_repo)
    return AuthService(user_service, session)


async def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    """Get user service dependency."""
    user_repo = UserRepository(session)
    return UserService(user_repo)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Register a new user with password validation."""
    return await auth_service.user_service.create_user(user_data)


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Login user and return access token with session tracking."""
    return await auth_service.login(login_data, request)


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
):
    """Change user password with validation."""
    await user_service.change_password(current_user["id"], password_data)
    return SuccessResponse(
        success=True,
        message="Password changed successfully"
    )


@router.post("/check-password-strength", response_model=PasswordStrengthResponse)
async def check_password_strength(
    password_data: PasswordStrengthCheck,
    user_service: UserService = Depends(get_user_service)
):
    """Check password strength and get feedback."""
    result = await user_service.check_password_strength(password_data.password)
    return PasswordStrengthResponse(**result)


@router.post("/request-password-reset", response_model=SuccessResponse)
async def request_password_reset(
    reset_data: PasswordReset,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Request password reset token."""
    result = await auth_service.request_password_reset(reset_data)
    return SuccessResponse(
        success=True,
        message=result["message"],
        data={"token": result.get("token")}  # Remove in production
    )


@router.post("/confirm-password-reset", response_model=SuccessResponse)
async def confirm_password_reset(
    reset_data: PasswordResetConfirm,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Confirm password reset with token."""
    result = await auth_service.confirm_password_reset(reset_data)
    return SuccessResponse(
        success=True,
        message=result["message"]
    )


@router.post("/unlock-account/{user_id}", response_model=SuccessResponse)
async def unlock_account(
    user_id: int,
    current_user: dict = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
):
    """Unlock user account (admin only)."""
    # Check if current user has admin role (implement role check)
    # For now, allow any authenticated user to unlock (should be restricted to admin)
    
    await user_service.unlock_user_account(user_id)
    return SuccessResponse(
        success=True,
        message="Account unlocked successfully"
    )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    session_id: str,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Logout from current session."""
    result = await auth_service.logout(session_id)
    return SuccessResponse(
        success=True,
        message=result["message"]
    )


@router.post("/logout-all", response_model=SuccessResponse)
async def logout_all_devices(
    current_user: dict = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Logout from all devices."""
    result = await auth_service.logout_all_devices(current_user["id"])
    return SuccessResponse(
        success=True,
        message=result["message"],
        data={"sessions_terminated": result["sessions_terminated"]}
    )


@router.post("/revoke-session/{session_id}", response_model=SuccessResponse)
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Revoke a specific session."""
    result = await auth_service.revoke_session(session_id)
    return SuccessResponse(
        success=True,
        message=result["message"]
    )


@router.get("/sessions", response_model=SuccessResponse)
async def get_user_sessions(
    current_user: dict = Depends(get_current_active_user)
):
    """Get all active sessions for current user."""
    sessions = await device_session_manager.get_user_session_details(current_user["id"])
    return SuccessResponse(
        success=True,
        message="Sessions retrieved successfully",
        data={"sessions": sessions}
    )
