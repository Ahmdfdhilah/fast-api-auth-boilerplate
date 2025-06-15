"""File upload endpoints."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.repositories.files import FileRepository
from src.services.files import FileService
from src.services.storage import StorageService
from src.schemas.files import (
    FileUploadResponse,
    FileListResponse,
    MultipleFileUploadResponse,
    FileDeleteResponse,
    FileUrlResponse,
    StorageInfoResponse
)
from src.auth.permissions import get_current_active_user, admin_required

router = APIRouter()


async def get_file_service(session: AsyncSession = Depends(get_db)) -> FileService:
    """Get file service dependency."""
    file_repo = FileRepository(session)
    storage_service = StorageService()
    return FileService(file_repo, storage_service)


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    folder: str = Form(""),
    is_public: bool = Form(False),
    is_temporary: bool = Form(False),
    expires_in_seconds: Optional[int] = Form(None),
    current_user: dict = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
):
    """Upload a single file."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    uploaded_file = await file_service.upload_file(
        file=file,
        user_id=current_user["id"],
        folder=folder,
        is_public=is_public,
        is_temporary=is_temporary,
        expires_in_seconds=expires_in_seconds
    )
    
    return uploaded_file


@router.post("/upload-multiple", response_model=MultipleFileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    folder: str = Form(""),
    is_public: bool = Form(False),
    is_temporary: bool = Form(False),
    expires_in_seconds: Optional[int] = Form(None),
    current_user: dict = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
):
    """Upload multiple files."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )
    
    result = await file_service.upload_multiple_files(
        files=files,
        user_id=current_user["id"],
        folder=folder,
        is_public=is_public,
        is_temporary=is_temporary,
        expires_in_seconds=expires_in_seconds
    )
    
    return MultipleFileUploadResponse(**result)


@router.get("/", response_model=FileListResponse)
async def get_all_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    folder: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    current_user: dict = Depends(admin_required),
    file_service: FileService = Depends(get_file_service)
):
    """Get all files (admin only)."""
    return await file_service.get_all_files(
        skip=skip,
        limit=limit,
        folder=folder,
        content_type=content_type
    )


@router.get("/my-files", response_model=FileListResponse)
async def get_my_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    folder: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
):
    """Get current user's files."""
    return await file_service.get_user_files(
        user_id=current_user["id"],
        skip=skip,
        limit=limit,
        folder=folder
    )


@router.get("/{file_id}", response_model=FileUploadResponse)
async def get_file(
    file_id: int,
    current_user: dict = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
):
    """Get file by ID."""
    is_admin = "admin" in current_user.get("roles", [])
    return await file_service.get_file(
        file_id=file_id,
        user_id=current_user["id"],
        is_admin=is_admin
    )


@router.get("/{file_id}/url", response_model=FileUrlResponse)
async def get_file_url(
    file_id: int,
    expires_in: Optional[int] = Query(None, ge=1, le=86400),  # Max 24 hours
    current_user: dict = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
):
    """Get file URL (with optional signed URL for private files)."""
    is_admin = "admin" in current_user.get("roles", [])
    url = await file_service.get_file_url(
        file_id=file_id,
        user_id=current_user["id"],
        expires_in=expires_in,
        is_admin=is_admin
    )
    
    response = FileUrlResponse(url=url)
    if expires_in:
        response.expires_in = expires_in
        from datetime import datetime, timedelta
        response.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    return response


@router.delete("/{file_id}", response_model=FileDeleteResponse)
async def delete_file(
    file_id: int,
    force_delete: bool = Query(False, description="Permanently delete file (admin only)"),
    current_user: dict = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
):
    """Delete file."""
    is_admin = "admin" in current_user.get("roles", [])
    
    # Only admins can force delete
    if force_delete and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can permanently delete files"
        )
    
    result = await file_service.delete_file(
        file_id=file_id,
        user_id=current_user["id"],
        is_admin=is_admin,
        force_delete=force_delete
    )
    
    return FileDeleteResponse(**result)


@router.get("/admin/stats")
async def get_file_stats(
    current_user: dict = Depends(admin_required),
    file_service: FileService = Depends(get_file_service)
):
    """Get file upload statistics (admin only)."""
    return await file_service.get_file_stats()


@router.post("/admin/cleanup")
async def cleanup_expired_files(
    current_user: dict = Depends(admin_required),
    file_service: FileService = Depends(get_file_service)
):
    """Clean up expired temporary files (admin only)."""
    return await file_service.cleanup_expired_files()


@router.get("/admin/storage-info", response_model=StorageInfoResponse)
async def get_storage_info(
    current_user: dict = Depends(admin_required),
    file_service: FileService = Depends(get_file_service)
):
    """Get storage configuration information (admin only)."""
    return await file_service.get_storage_info()