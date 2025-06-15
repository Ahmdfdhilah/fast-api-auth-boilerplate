"""User endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.repositories.user import UserRepository
from src.services.user import UserService
from src.schemas.user import UserResponse, UserCreate, UserUpdate, UserListResponse
from src.auth.permissions import get_current_active_user, admin_required

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


@router.get("/", response_model=list[UserResponse])
async def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(admin_required),
    user_service: UserService = Depends(get_user_service)
):
    """Get all users (admin only)."""
    users = await user_service.get_all_users(skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: dict = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
):
    """Get specific user by ID."""
    # Users can get their own info, admins can get any user's info
    if current_user["id"] != user_id and "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's information"
        )
    
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(admin_required),
    user_service: UserService = Depends(get_user_service)
):
    """Create a new user (admin only)."""
    user = await user_service.create_user(user_data)
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
):
    """Update user."""
    # Users can update their own info, admins can update any user's info
    if current_user["id"] != user_id and "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's information"
        )
    
    user = await user_service.update_user(user_id, user_data)
    return user


@router.delete("/{user_id}", response_model=UserResponse)
async def delete_user(
    user_id: int,
    current_user: dict = Depends(admin_required),
    user_service: UserService = Depends(get_user_service)
):
    """Delete user (soft delete, admin only)."""
    if current_user["id"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user = await user_service.delete_user(user_id)
    return user