"""News service layer."""

from typing import List, Optional, Tuple
from math import ceil

from src.repositories.news import NewsRepository
from src.schemas.news import NewsCreate, NewsUpdate, NewsResponse, NewsListResponse
from src.models.news import News


class NewsService:
    """Service layer for news operations."""
    
    def __init__(self, news_repo: NewsRepository):
        self.news_repo = news_repo

    async def get_news(self, news_id: int) -> Optional[NewsResponse]:
        """Get news by ID."""
        news = await self.news_repo.get_by_id(news_id)
        if not news:
            return None
        return NewsResponse.model_validate(news)

    async def get_news_list(
        self, 
        page: int = 1, 
        per_page: int = 10, 
        published_only: bool = True
    ) -> NewsListResponse:
        """Get paginated news list."""
        news_list, total = await self.news_repo.get_all(page, per_page, published_only)
        
        items = [NewsResponse.model_validate(news) for news in news_list]
        pages = ceil(total / per_page) if total > 0 else 1
        
        return NewsListResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )

    async def create_news(self, news_data: NewsCreate, author_id: int) -> NewsResponse:
        """Create new news."""
        news = await self.news_repo.create(news_data, author_id)
        return NewsResponse.model_validate(news)

    async def update_news(
        self, 
        news_id: int, 
        news_data: NewsUpdate, 
        updated_by: int
    ) -> Optional[NewsResponse]:
        """Update news."""
        news = await self.news_repo.update(news_id, news_data, updated_by)
        if not news:
            return None
        return NewsResponse.model_validate(news)

    async def delete_news(self, news_id: int, deleted_by: int) -> bool:
        """Delete news (soft delete)."""
        news = await self.news_repo.soft_delete(news_id, deleted_by)
        return news is not None

    async def search_news(
        self, 
        query: str, 
        page: int = 1, 
        per_page: int = 10,
        published_only: bool = True
    ) -> NewsListResponse:
        """Search news."""
        news_list, total = await self.news_repo.search(query, page, per_page, published_only)
        
        items = [NewsResponse.model_validate(news) for news in news_list]
        pages = ceil(total / per_page) if total > 0 else 1
        
        return NewsListResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )