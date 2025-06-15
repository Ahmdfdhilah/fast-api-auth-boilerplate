"""MFA endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import get_auth_service
from src.core.database import get_db
from src.auth.permissions import get_current_active_user, admin_required
from src.auth.mfa import MFAService, MFAAdminService
from src.schemas.mfa import (
    MFAEnableRequest, MFAEnableResponse, MFAVerifyRequest, MFAVerifyResponse,
    MFADisableRequest, MFAStatusResponse, MFAStatsResponse, BackupCodesResponse
)
from ...services.auth import AuthService

router = APIRouter()


@router.post("/enable", response_model=MFAEnableResponse)
async def enable_mfa(
    request: MFAEnableRequest,
    current_user: dict = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Enable MFA for the current user.
    
    Returns TOTP secret, QR code URL, and backup codes.
    User must verify with TOTP code to complete setup.
    """
    mfa_service = MFAService(session)
    result = await mfa_service.enable_mfa(current_user["id"])
    
    return MFAEnableResponse(
        secret=result["secret"],
        qr_code_url=result["qr_code_url"],
        backup_codes=result["backup_codes"]
    )


@router.post("/verify", response_model=MFAVerifyResponse)
async def verify_mfa_setup(
    request: MFAVerifyRequest,
    current_user: dict = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Verify MFA setup with TOTP code and complete MFA enabling.
    """
    mfa_service = MFAService(session)
    
    try:
        success = await mfa_service.verify_and_enable_mfa(current_user["id"], request.code)
        
        if success:
            return MFAVerifyResponse(
                success=True,
                message="MFA has been successfully enabled"
            )
        else:
            return MFAVerifyResponse(
                success=False,
                message="Invalid verification code"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify MFA setup"
        )


@router.post("/disable", response_model=MFAVerifyResponse)
async def disable_mfa(
    request: MFADisableRequest,
    current_user: dict = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Disable MFA for the current user.
    Requires TOTP code verification.
    """
    mfa_service = MFAService(session)
    
    try:
        success = await mfa_service.disable_mfa(current_user["id"], request.code)
        
        if success:
            return MFAVerifyResponse(
                success=True,
                message="MFA has been successfully disabled"
            )
        else:
            return MFAVerifyResponse(
                success=False,
                message="Invalid verification code"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable MFA"
        )


@router.get("/status", response_model=MFAStatusResponse)
async def get_mfa_status(
    current_user: dict = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Get MFA status for the current user."""
    mfa_service = MFAService(session)
    status_data = await mfa_service.get_mfa_status(current_user["id"])
    
    return MFAStatusResponse(
        mfa_enabled=status_data["mfa_enabled"],
        backup_codes_remaining=status_data["backup_codes_remaining"]
    )


@router.post("/backup-codes/regenerate", response_model=BackupCodesResponse)
async def regenerate_backup_codes(
    current_user: dict = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Regenerate backup codes for the current user."""
    mfa_service = MFAService(session)
    new_codes = await mfa_service.regenerate_backup_codes(current_user["id"])
    
    return BackupCodesResponse(backup_codes=new_codes)


# Admin endpoints
@router.post("/admin/disable/{user_id}", response_model=MFAVerifyResponse)
async def admin_disable_mfa(
    user_id: int,
    current_user: dict = Depends(admin_required),
    session: AsyncSession = Depends(get_db)
):
    """
    Force disable MFA for a user (admin only).
    Does not require MFA code verification.
    """
    admin_service = MFAAdminService(session)
    
    try:
        success = await admin_service.force_disable_mfa(user_id)
        
        if success:
            return MFAVerifyResponse(
                success=True,
                message=f"MFA has been disabled for user {user_id}"
            )
        else:
            return MFAVerifyResponse(
                success=False,
                message=f"User {user_id} does not have MFA enabled"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable MFA for user"
        )

@router.post("/mfa/backup-codes/regenerate", response_model=dict)
async def regenerate_backup_codes(
    current_user: dict = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Regenerate backup codes for the current user."""
    from src.auth.mfa import MFAService
    mfa_service = MFAService(auth_service.session)
    
    new_codes = await mfa_service.regenerate_backup_codes(current_user["id"])
    
    return {
        "success": True,
        "message": "Backup codes regenerated successfully",
        "data": {"backup_codes": new_codes}
    }


@router.get("/admin/stats", response_model=MFAStatsResponse)
async def get_mfa_stats(
    current_user: dict = Depends(admin_required),
    session: AsyncSession = Depends(get_db)
):
    """Get MFA usage statistics (admin only)."""
    admin_service = MFAAdminService(session)
    stats = await admin_service.get_mfa_stats()
    
    return MFAStatsResponse(
        total_users=stats["total_users"],
        mfa_enabled_users=stats["mfa_enabled_users"],
        mfa_adoption_rate=stats["mfa_adoption_rate"]
    )
