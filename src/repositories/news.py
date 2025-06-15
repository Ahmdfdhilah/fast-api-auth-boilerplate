"""News repository for database operations."""

from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.news import News
from src.schemas.news import NewsCreate, NewsUpdate


class NewsRepository:
    """Repository for news operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, news_id: int) -> Optional[News]:
        """Get news by ID."""
        query = select(News).where(
            and_(News.id == news_id, News.deleted_at.is_(None))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self, 
        page: int = 1, 
        per_page: int = 10, 
        published_only: bool = True
    ) -> Tuple[List[News], int]:
        """Get paginated news list."""
        offset = (page - 1) * per_page
        
        # Base query
        base_query = select(News).where(News.deleted_at.is_(None))
        
        if published_only:
            base_query = base_query.where(News.is_published == True)
        
        # Count query
        count_query = select(func.count(News.id)).where(News.deleted_at.is_(None))
        if published_only:
            count_query = count_query.where(News.is_published == True)
        
        # Execute count query
        count_result = await self.session.execute(count_query)
        total = count_result.scalar()
        
        # Execute main query with pagination
        query = base_query.order_by(desc(News.published_at)).offset(offset).limit(per_page)
        result = await self.session.execute(query)
        news_list = result.scalars().all()
        
        return news_list, total

    async def create(self, news_data: NewsCreate, author_id: int) -> News:
        """Create new news."""
        news = News(
            title=news_data.title,
            content=news_data.content,
            is_published=news_data.is_published,
            author_id=author_id,
            created_by=author_id
        )
        self.session.add(news)
        await self.session.commit()
        await self.session.refresh(news)
        return news

    async def update(self, news_id: int, news_data: NewsUpdate, updated_by: int) -> Optional[News]:
        """Update news."""
        news = await self.get_by_id(news_id)
        if not news:
            return None

        update_data = news_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(news, key, value)

        news.updated_at = datetime.utcnow()
        news.updated_by = updated_by
        
        await self.session.commit()
        await self.session.refresh(news)
        return news

    async def soft_delete(self, news_id: int, deleted_by: int) -> Optional[News]:
        """Soft delete news."""
        news = await self.get_by_id(news_id)
        if not news:
            return None

        news.deleted_at = datetime.utcnow()
        news.deleted_by = deleted_by
        
        await self.session.commit()
        await self.session.refresh(news)
        return news

    async def search(
        self, 
        query_text: str, 
        page: int = 1, 
        per_page: int = 10,
        published_only: bool = True
    ) -> Tuple[List[News], int]:
        """Search news by title or content."""
        offset = (page - 1) * per_page
        
        # Base query with search
        base_query = select(News).where(
            and_(
                News.deleted_at.is_(None),
                (News.title.ilike(f"%{query_text}%") | News.content.ilike(f"%{query_text}%"))
            )
        )
        
        if published_only:
            base_query = base_query.where(News.is_published == True)
        
        # Count query
        count_query = select(func.count(News.id)).where(
            and_(
                News.deleted_at.is_(None),
                (News.title.ilike(f"%{query_text}%") | News.content.ilike(f"%{query_text}%"))
            )
        )
        if published_only:
            count_query = count_query.where(News.is_published == True)
        
        # Execute count query
        count_result = await self.session.execute(count_query)
        total = count_result.scalar()
        
        # Execute main query with pagination
        query = base_query.order_by(desc(News.published_at)).offset(offset).limit(per_page)
        result = await self.session.execute(query)
        news_list = result.scalars().all()
        
        return news_list, total