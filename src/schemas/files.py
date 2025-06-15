"""File upload schemas."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime


class FileUploadResponse(BaseModel):
    """Response schema for file upload."""
    id: int
    filename: str
    original_filename: str
    file_path: str
    file_url: str
    content_type: str
    file_size: int
    folder: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(None, alias="file_metadata")
    uploaded_by: int
    uploaded_at: datetime = Field(alias="created_at")
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FileListResponse(BaseModel):
    """Response schema for file list."""
    files: List[FileUploadResponse]
    total: int
    skip: int
    limit: int


class MultipleFileUploadResponse(BaseModel):
    """Response schema for multiple file upload."""
    uploaded_files: List[FileUploadResponse]
    failed_files: Optional[List[Dict[str, str]]] = None
    total_uploaded: int
    total_failed: int


class FileInfoResponse(BaseModel):
    """Response schema for file info without database fields."""
    filename: str
    content_type: str
    size: int
    url: str
    key: str
    metadata: Optional[Dict[str, Any]] = None
    uploaded_at: Optional[datetime] = None


class StorageInfoResponse(BaseModel):
    """Response schema for storage configuration info."""
    provider: str
    max_file_size: int
    max_filename_length: int
    allowed_file_types: List[str]
    uploads_path: Optional[str] = None


class FileDeleteResponse(BaseModel):
    """Response schema for file deletion."""
    success: bool
    message: str
    filename: Optional[str] = None


class FileUrlResponse(BaseModel):
    """Response schema for file URL generation."""
    url: str
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None