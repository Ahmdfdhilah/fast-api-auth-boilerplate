"""News endpoints for admin operations."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.repositories.news import NewsRepository
from src.services.news import NewsService
from src.schemas.news import (
    NewsCreate, 
    NewsUpdate, 
    NewsResponse, 
    NewsListResponse
)
from src.auth.permissions import get_current_active_user, admin_required

router = APIRouter()


async def get_news_service(session: AsyncSession = Depends(get_db)) -> NewsService:
    """Get news service dependency."""
    news_repo = NewsRepository(session)
    return NewsService(news_repo)


@router.get("/", response_model=NewsListResponse)
async def get_news_list(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    published_only: bool = Query(True, description="Show only published news"),
    news_service: NewsService = Depends(get_news_service)
):
    """Get paginated news list."""
    return await news_service.get_news_list(page, per_page, published_only)


@router.get("/search", response_model=NewsListResponse)
async def search_news(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    published_only: bool = Query(True, description="Show only published news"),
    news_service: NewsService = Depends(get_news_service)
):
    """Search news."""
    return await news_service.search_news(q, page, per_page, published_only)


@router.get("/{news_id}", response_model=NewsResponse)
async def get_news(
    news_id: int,
    news_service: NewsService = Depends(get_news_service)
):
    """Get news by ID."""
    news = await news_service.get_news(news_id)
    if not news:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="News not found"
        )
    return news


@router.post("/", response_model=NewsResponse, status_code=status.HTTP_201_CREATED)
async def create_news(
    news_data: NewsCreate,
    current_user: dict = Depends(admin_required),
    news_service: NewsService = Depends(get_news_service)
):
    """Create new news (admin only)."""
    return await news_service.create_news(news_data, current_user["id"])


@router.put("/{news_id}", response_model=NewsResponse)
async def update_news(
    news_id: int,
    news_data: NewsUpdate,
    current_user: dict = Depends(admin_required),
    news_service: NewsService = Depends(get_news_service)
):
    """Update news (admin only)."""
    news = await news_service.update_news(news_id, news_data, current_user["id"])
    if not news:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="News not found"
        )
    return news


@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news(
    news_id: int,
    current_user: dict = Depends(admin_required),
    news_service: NewsService = Depends(get_news_service)
):
    """Delete news (admin only)."""
    success = await news_service.delete_news(news_id, current_user["id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="News not found"
        )