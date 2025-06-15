"""Storage service with factory pattern."""

from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status

from src.utils.storage import StorageInterface, StorageProvider, FileInfo
from src.utils.storage_providers import (
    LocalStorageProvider,
    AWSS3StorageProvider,
    GCPStorageProvider,
    AzureBlobStorageProvider
)
from src.core.config import settings


class StorageFactory:
    """Factory for creating storage providers."""
    
    @staticmethod
    def create_storage_provider(provider: str = None) -> StorageInterface:
        """Create storage provider based on configuration."""
        provider = provider or settings.STORAGE_PROVIDER
        
        if provider == StorageProvider.LOCAL:
            return LocalStorageProvider()
        elif provider == StorageProvider.AWS_S3:
            return AWSS3StorageProvider()
        elif provider == StorageProvider.GCP:
            return GCPStorageProvider()
        elif provider == StorageProvider.AZURE_BLOB:
            return AzureBlobStorageProvider()
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unsupported storage provider: {provider}"
            )


class StorageService:
    """High-level storage service."""
    
    def __init__(self, storage_provider: StorageInterface = None):
        self.storage = storage_provider or StorageFactory.create_storage_provider()
    
    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str = None,
        folder: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        validate: bool = True
    ) -> FileInfo:
        """Upload file with validation."""
        
        if validate:
            # Validate file size
            if not self.storage.validate_file_size(len(file_data), settings.MAX_UPLOAD_SIZE):
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE} bytes"
                )
            
            # Validate filename length
            if len(filename) > settings.MAX_FILENAME_LENGTH:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Filename exceeds maximum length of {settings.MAX_FILENAME_LENGTH} characters"
                )
            
            # Determine content type if not provided
            if not content_type:
                content_type = self.storage.get_content_type(filename)
            
            # Validate file type
            allowed_types = settings.ALLOWED_FILE_TYPES_LIST
            if not self.storage.validate_file_type(content_type, allowed_types):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File type '{content_type}' not allowed. Allowed types: {', '.join(allowed_types)}"
                )
        
        return await self.storage.upload_file(
            file_data=file_data,
            filename=filename,
            content_type=content_type,
            folder=folder,
            metadata=metadata
        )
    
    async def delete_file(self, key: str) -> bool:
        """Delete file."""
        return await self.storage.delete_file(key)
    
    async def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get file URL."""
        return await self.storage.get_file_url(key, expires_in)
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists."""
        return await self.storage.file_exists(key)
    
    async def list_files(self, folder: str = "", limit: int = 100) -> List[FileInfo]:
        """List files."""
        return await self.storage.list_files(folder, limit)
    
    async def upload_multiple_files(
        self,
        files_data: List[Dict[str, Any]],
        folder: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[FileInfo]:
        """Upload multiple files."""
        uploaded_files = []
        failed_files = []
        
        for file_data in files_data:
            try:
                file_info = await self.upload_file(
                    file_data=file_data["data"],
                    filename=file_data["filename"],
                    content_type=file_data.get("content_type"),
                    folder=folder,
                    metadata=metadata
                )
                uploaded_files.append(file_info)
            except HTTPException as e:
                failed_files.append({
                    "filename": file_data["filename"],
                    "error": e.detail
                })
        
        if failed_files and not uploaded_files:
            # All files failed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "All files failed to upload", "failed_files": failed_files}
            )
        elif failed_files:
            # Some files failed
            raise HTTPException(
                status_code=status.HTTP_207_MULTI_STATUS,
                detail={
                    "message": "Some files failed to upload",
                    "uploaded_files": [{"filename": f.filename, "url": f.url} for f in uploaded_files],
                    "failed_files": failed_files
                }
            )
        
        return uploaded_files
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get current storage configuration info."""
        return {
            "provider": settings.STORAGE_PROVIDER,
            "max_file_size": settings.MAX_UPLOAD_SIZE,
            "max_filename_length": settings.MAX_FILENAME_LENGTH,
            "allowed_file_types": settings.ALLOWED_FILE_TYPES_LIST,
            "uploads_path": settings.UPLOADS_PATH if settings.STORAGE_PROVIDER == "local" else None
        }