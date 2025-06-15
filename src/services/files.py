"""File upload service."""

from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status, UploadFile

from src.repositories.files import FileRepository
from src.services.storage import StorageService
from src.schemas.files import FileUploadResponse, FileListResponse
from src.models.files import FileUpload
from src.utils.storage import FileInfo


class FileService:
    """Service for file upload operations."""
    
    def __init__(self, file_repo: FileRepository, storage_service: StorageService = None):
        self.file_repo = file_repo
        self.storage_service = storage_service or StorageService()
    
    async def upload_file(
        self,
        file: UploadFile,
        user_id: int,
        folder: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        is_public: bool = False,
        is_temporary: bool = False,
        expires_in_seconds: Optional[int] = None
    ) -> FileUploadResponse:
        """Upload a single file."""
        
        # Read file data
        file_data = await file.read()
        
        # Upload to storage
        file_info: FileInfo = await self.storage_service.upload_file(
            file_data=file_data,
            filename=file.filename,
            content_type=file.content_type,
            folder=folder,
            metadata=metadata
        )
        
        # Create database record
        file_record = await self.file_repo.create_file_record(
            filename=file_info.key,
            original_filename=file.filename,
            file_path=file_info.key,
            file_url=file_info.url,
            content_type=file_info.content_type,
            file_size=file_info.size,
            uploaded_by=user_id,
            folder=folder,
            file_metadata=file_info.metadata,
            is_public=is_public,
            is_temporary=is_temporary,
            expires_in_seconds=expires_in_seconds,
            storage_provider=self.storage_service.storage.__class__.__name__.replace('StorageProvider', '').lower()
        )
        
        return FileUploadResponse.model_validate(file_record)
    
    async def upload_multiple_files(
        self,
        files: List[UploadFile],
        user_id: int,
        folder: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        is_public: bool = False,
        is_temporary: bool = False,
        expires_in_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Upload multiple files."""
        uploaded_files = []
        failed_files = []
        
        for file in files:
            try:
                uploaded_file = await self.upload_file(
                    file=file,
                    user_id=user_id,
                    folder=folder,
                    metadata=metadata,
                    is_public=is_public,
                    is_temporary=is_temporary,
                    expires_in_seconds=expires_in_seconds
                )
                uploaded_files.append(uploaded_file)
            except HTTPException as e:
                failed_files.append({
                    "filename": file.filename,
                    "error": e.detail
                })
            except Exception as e:
                failed_files.append({
                    "filename": file.filename,
                    "error": str(e)
                })
        
        return {
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "total_uploaded": len(uploaded_files),
            "total_failed": len(failed_files)
        }
    
    async def get_file(self, file_id: int, user_id: int, is_admin: bool = False) -> FileUploadResponse:
        """Get file by ID with access control."""
        file_record = await self.file_repo.get_file_by_id(file_id)
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check access permissions
        if not is_admin and file_record.uploaded_by != user_id and not file_record.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return FileUploadResponse.model_validate(file_record)
    
    async def get_user_files(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        folder: Optional[str] = None
    ) -> FileListResponse:
        """Get files uploaded by user."""
        files = await self.file_repo.get_files_by_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            folder=folder
        )
        
        total = await self.file_repo.count_files_by_user(user_id)
        
        return FileListResponse(
            files=[FileUploadResponse.model_validate(f) for f in files],
            total=total,
            skip=skip,
            limit=limit
        )
    
    async def get_all_files(
        self,
        skip: int = 0,
        limit: int = 100,
        folder: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> FileListResponse:
        """Get all files (admin only)."""
        files = await self.file_repo.get_all_files(
            skip=skip,
            limit=limit,
            folder=folder,
            content_type=content_type
        )
        
        total = await self.file_repo.count_all_files()
        
        return FileListResponse(
            files=[FileUploadResponse.model_validate(f) for f in files],
            total=total,
            skip=skip,
            limit=limit
        )
    
    async def delete_file(
        self,
        file_id: int,
        user_id: int,
        is_admin: bool = False,
        force_delete: bool = False
    ) -> Dict[str, Any]:
        """Delete file with access control."""
        file_record = await self.file_repo.get_file_by_id(file_id)
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check access permissions
        if not is_admin and file_record.uploaded_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Delete from storage
        storage_deleted = await self.storage_service.delete_file(file_record.file_path)
        
        # Delete from database
        if force_delete:
            db_deleted = await self.file_repo.hard_delete_file(file_id)
        else:
            deleted_file = await self.file_repo.soft_delete_file(file_id)
            db_deleted = deleted_file is not None
        
        return {
            "success": storage_deleted and db_deleted,
            "message": "File deleted successfully" if (storage_deleted and db_deleted) else "File deletion failed",
            "filename": file_record.original_filename,
            "storage_deleted": storage_deleted,
            "database_deleted": db_deleted
        }
    
    async def get_file_url(
        self,
        file_id: int,
        user_id: int,
        expires_in: Optional[int] = None,
        is_admin: bool = False
    ) -> str:
        """Get file URL with access control."""
        file_record = await self.file_repo.get_file_by_id(file_id)
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check access permissions
        if not is_admin and file_record.uploaded_by != user_id and not file_record.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get URL from storage service
        url = await self.storage_service.get_file_url(file_record.file_path, expires_in)
        
        # Update database record if URL changed (for signed URLs)
        if url != file_record.file_url:
            await self.file_repo.update_file_url(file_id, url)
        
        return url
    
    async def get_file_stats(self) -> Dict[str, Any]:
        """Get file upload statistics."""
        return await self.file_repo.get_file_stats()
    
    async def cleanup_expired_files(self) -> Dict[str, Any]:
        """Clean up expired temporary files."""
        # Get expired files
        expired_files = await self.file_repo.get_expired_temporary_files()
        
        deleted_count = 0
        failed_count = 0
        
        for file_record in expired_files:
            try:
                # Delete from storage
                await self.storage_service.delete_file(file_record.file_path)
                deleted_count += 1
            except Exception:
                failed_count += 1
        
        # Soft delete from database
        db_deleted_count = await self.file_repo.cleanup_expired_files()
        
        return {
            "total_expired": len(expired_files),
            "storage_deleted": deleted_count,
            "storage_failed": failed_count,
            "database_deleted": db_deleted_count
        }
    
    async def get_storage_info(self) -> Dict[str, Any]:
        """Get storage configuration information."""
        return self.storage_service.get_storage_info()