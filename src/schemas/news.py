"""News schemas for request/response validation."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class NewsBase(BaseModel):
    """Base news schema."""
    title: str = Field(max_length=255, description="News title")
    content: str = Field(description="News content")
    is_published: bool = Field(default=True, description="Whether the news is published")


class NewsCreate(NewsBase):
    """Schema for creating news."""
    pass


class NewsUpdate(BaseModel):
    """Schema for updating news."""
    title: Optional[str] = Field(None, max_length=255, description="News title")
    content: Optional[str] = Field(None, description="News content")
    is_published: Optional[bool] = Field(None, description="Whether the news is published")


class NewsResponse(NewsBase):
    """Schema for news response."""
    id: int
    author_id: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class NewsListResponse(BaseModel):
    """Schema for paginated news list response."""
    items: list[NewsResponse]
    total: int
    page: int
    per_page: int
    pages: int