"""Storage abstraction layer for file uploads."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from enum import Enum
import os
import uuid
import mimetypes
from datetime import datetime
from pathlib import Path


class StorageProvider(str, Enum):
    """Supported storage providers."""
    LOCAL = "local"
    AWS_S3 = "aws_s3"
    GCP = "gcp"
    AZURE_BLOB = "azure_blob"


class FileInfo:
    """File information container."""
    def __init__(
        self,
        filename: str,
        content_type: str,
        size: int,
        url: str,
        key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.filename = filename
        self.content_type = content_type
        self.size = size
        self.url = url
        self.key = key or filename
        self.metadata = metadata or {}
        self.uploaded_at = datetime.utcnow()


class StorageInterface(ABC):
    """Abstract storage interface."""
    
    @abstractmethod
    async def upload_file(
        self, 
        file_data: bytes, 
        filename: str, 
        content_type: str,
        folder: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> FileInfo:
        """Upload file and return file info."""
        pass
    
    @abstractmethod
    async def delete_file(self, key: str) -> bool:
        """Delete file by key/path."""
        pass
    
    @abstractmethod
    async def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get file URL (signed URL for private files)."""
        pass
    
    @abstractmethod
    async def file_exists(self, key: str) -> bool:
        """Check if file exists."""
        pass
    
    @abstractmethod
    async def list_files(self, folder: str = "", limit: int = 100) -> List[FileInfo]:
        """List files in folder."""
        pass

    def generate_unique_filename(self, original_filename: str, folder: str = "") -> str:
        """Generate unique filename to prevent conflicts."""
        file_ext = Path(original_filename).suffix
        unique_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{timestamp}_{unique_id}{file_ext}"
        
        if folder:
            return f"{folder.strip('/')}/{new_filename}"
        return new_filename

    def validate_file_type(self, content_type: str, allowed_types: List[str]) -> bool:
        """Validate file content type."""
        return content_type in allowed_types

    def validate_file_size(self, size: int, max_size: int) -> bool:
        """Validate file size."""
        return size <= max_size

    def get_content_type(self, filename: str) -> str:
        """Get content type from filename."""
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"