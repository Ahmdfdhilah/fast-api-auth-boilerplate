"""File upload models."""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column, JSON

from .base import BaseModel


class FileUpload(BaseModel, SQLModel, table=True):
    """File upload model."""
    
    __tablename__ = "file_uploads"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True)  # Generated unique filename
    original_filename: str  # Original filename from user
    file_path: str  # Storage path/key
    file_url: str  # Public URL or signed URL
    content_type: str
    file_size: int  # Size in bytes
    folder: Optional[str] = Field(default=None, index=True)  # Organization folder
    file_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))  # Additional metadata
    
    # User association
    uploaded_by: int = Field(foreign_key="users.id", index=True)
    
    # File status
    is_public: bool = Field(default=False)  # Whether file is publicly accessible
    is_temporary: bool = Field(default=False)  # Whether file should be cleaned up
    expires_at: Optional[datetime] = Field(default=None)  # For temporary files
    
    # Storage provider info
    storage_provider: str = Field(default="local")  # Which storage provider was used
    
    def is_expired(self) -> bool:
        """Check if temporary file has expired."""
        if not self.is_temporary or not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get file information as dictionary."""
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "file_url": self.file_url,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "folder": self.folder,
            "metadata": self.file_metadata,
            "uploaded_by": self.uploaded_by,
            "uploaded_at": self.created_at,
            "is_public": self.is_public,
            "is_temporary": self.is_temporary,
            "expires_at": self.expires_at,
            "storage_provider": self.storage_provider
        }