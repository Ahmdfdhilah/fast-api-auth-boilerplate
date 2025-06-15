"""API router configuration."""

from fastapi import APIRouter

from src.api.endpoints import auth, users, mfa, files

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(mfa.router, prefix="/mfa", tags=["multi-factor-authentication"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
