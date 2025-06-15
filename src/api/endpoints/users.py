"""User endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.repositories.user import UserRepository
from src.services.user import UserService
from src.schemas.user import UserResponse
from src.auth.permissions import get_current_active_user

router = APIRouter()

async def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    """Get user service dependency."""
    user_repo = UserRepository(session)
    return UserService(user_repo)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
):
    """Get current user information."""
    user = await user_service.get_user(current_user["id"])
    return user