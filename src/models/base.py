"""Base model with common fields."""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class TimestampMixin(SQLModel):
    """Mixin for timestamp fields."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)


class SoftDeleteMixin(SQLModel):
    """Mixin for soft delete functionality."""
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[int] = Field(default=None)


class AuditMixin(SQLModel):
    """Mixin for audit fields."""
    created_by: Optional[int] = Field(default=None)
    updated_by: Optional[int] = Field(default=None)


class BaseModel(TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Base model with all common fields."""
    pass
