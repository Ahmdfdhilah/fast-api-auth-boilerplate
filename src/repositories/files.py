"""File upload repository."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.files import FileUpload


class FileRepository:
    """Repository for file upload operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_file_record(
        self,
        filename: str,
        original_filename: str,
        file_path: str,
        file_url: str,
        content_type: str,
        file_size: int,
        uploaded_by: int,
        folder: Optional[str] = None,
        file_metadata: Optional[Dict[str, Any]] = None,
        is_public: bool = False,
        is_temporary: bool = False,
        expires_in_seconds: Optional[int] = None,
        storage_provider: str = "local"
    ) -> FileUpload:
        """Create file upload record."""
        expires_at = None
        if is_temporary and expires_in_seconds:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
        
        file_record = FileUpload(
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_url=file_url,
            content_type=content_type,
            file_size=file_size,
            folder=folder,
            file_metadata=file_metadata,
            uploaded_by=uploaded_by,
            is_public=is_public,
            is_temporary=is_temporary,
            expires_at=expires_at,
            storage_provider=storage_provider
        )
        
        self.session.add(file_record)
        await self.session.commit()
        await self.session.refresh(file_record)
        return file_record
    
    async def get_file_by_id(self, file_id: int) -> Optional[FileUpload]:
        """Get file by ID."""
        query = select(FileUpload).where(
            and_(FileUpload.id == file_id, FileUpload.deleted_at.is_(None))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_file_by_path(self, file_path: str) -> Optional[FileUpload]:
        """Get file by file path."""
        query = select(FileUpload).where(
            and_(FileUpload.file_path == file_path, FileUpload.deleted_at.is_(None))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_files_by_user(
        self, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100,
        folder: Optional[str] = None
    ) -> List[FileUpload]:
        """Get files by user with pagination."""
        conditions = [
            FileUpload.uploaded_by == user_id,
            FileUpload.deleted_at.is_(None)
        ]
        
        if folder is not None:
            conditions.append(FileUpload.folder == folder)
        
        query = (
            select(FileUpload)
            .where(and_(*conditions))
            .offset(skip)
            .limit(limit)
            .order_by(FileUpload.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_all_files(
        self, 
        skip: int = 0, 
        limit: int = 100,
        folder: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> List[FileUpload]:
        """Get all files with pagination and filters."""
        conditions = [FileUpload.deleted_at.is_(None)]
        
        if folder is not None:
            conditions.append(FileUpload.folder == folder)
        
        if content_type is not None:
            conditions.append(FileUpload.content_type == content_type)
        
        query = (
            select(FileUpload)
            .where(and_(*conditions))
            .offset(skip)
            .limit(limit)
            .order_by(FileUpload.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def count_files_by_user(self, user_id: int) -> int:
        """Count files by user."""
        query = select(FileUpload).where(
            and_(
                FileUpload.uploaded_by == user_id,
                FileUpload.deleted_at.is_(None)
            )
        )
        result = await self.session.execute(query)
        return len(result.scalars().all())
    
    async def count_all_files(self) -> int:
        """Count all files."""
        query = select(FileUpload).where(FileUpload.deleted_at.is_(None))
        result = await self.session.execute(query)
        return len(result.scalars().all())
    
    async def update_file_url(self, file_id: int, new_url: str) -> Optional[FileUpload]:
        """Update file URL (useful for signed URLs)."""
        file_record = await self.get_file_by_id(file_id)
        if not file_record:
            return None
        
        file_record.file_url = new_url
        file_record.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(file_record)
        return file_record
    
    async def soft_delete_file(self, file_id: int) -> Optional[FileUpload]:
        """Soft delete file record."""
        file_record = await self.get_file_by_id(file_id)
        if not file_record:
            return None
        
        file_record.deleted_at = datetime.utcnow()
        file_record.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(file_record)
        return file_record
    
    async def hard_delete_file(self, file_id: int) -> bool:
        """Hard delete file record."""
        query = delete(FileUpload).where(FileUpload.id == file_id)
        result = await self.session.execute(query)
        await self.session.commit()
        return result.rowcount > 0
    
    async def get_expired_temporary_files(self) -> List[FileUpload]:
        """Get expired temporary files for cleanup."""
        query = select(FileUpload).where(
            and_(
                FileUpload.is_temporary == True,
                FileUpload.expires_at < datetime.utcnow(),
                FileUpload.deleted_at.is_(None)
            )
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_files_by_folder(self, folder: str) -> List[FileUpload]:
        """Get all files in a specific folder."""
        query = select(FileUpload).where(
            and_(
                FileUpload.folder == folder,
                FileUpload.deleted_at.is_(None)
            )
        ).order_by(FileUpload.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_file_stats(self) -> Dict[str, Any]:
        """Get file upload statistics."""
        # Total files
        total_query = select(FileUpload).where(FileUpload.deleted_at.is_(None))
        total_result = await self.session.execute(total_query)
        total_files = len(total_result.scalars().all())
        
        # Public files
        public_query = select(FileUpload).where(
            and_(FileUpload.is_public == True, FileUpload.deleted_at.is_(None))
        )
        public_result = await self.session.execute(public_query)
        public_files = len(public_result.scalars().all())
        
        # Temporary files
        temp_query = select(FileUpload).where(
            and_(FileUpload.is_temporary == True, FileUpload.deleted_at.is_(None))
        )
        temp_result = await self.session.execute(temp_query)
        temp_files = len(temp_result.scalars().all())
        
        # Calculate total storage used
        all_files = total_result.scalars().all()
        total_storage = sum(file.file_size for file in all_files)
        
        return {
            "total_files": total_files,
            "public_files": public_files,
            "temporary_files": temp_files,
            "total_storage_bytes": total_storage,
            "total_storage_mb": round(total_storage / (1024 * 1024), 2)
        }
    
    async def cleanup_expired_files(self) -> int:
        """Soft delete expired temporary files and return count."""
        expired_files = await self.get_expired_temporary_files()
        count = 0
        
        for file_record in expired_files:
            file_record.deleted_at = datetime.utcnow()
            file_record.updated_at = datetime.utcnow()
            count += 1
        
        if count > 0:
            await self.session.commit()
        
        return count