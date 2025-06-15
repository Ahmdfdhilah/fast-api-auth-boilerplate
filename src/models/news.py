"""News model."""

from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship

from .base import BaseModel


class News(BaseModel, SQLModel, table=True):
    """News model for managing news articles."""
    
    __tablename__ = "news"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=255, index=True)
    content: str
    author_id: Optional[int] = Field(default=None, foreign_key="users.id")
    published_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    is_published: bool = Field(default=True)
    
    # Relationship
    author: Optional["User"] = Relationship()
    
    def __repr__(self) -> str:
        return f"<News(id={self.id}, title='{self.title[:30]}...')>"