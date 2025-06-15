"""User repository MFA methods."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime

from src.models.user import User, MFABackupCode


class UserMFARepository:
    """User repository with MFA-specific methods."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_mfa_secret(self, user_id: int, secret: Optional[str], enabled: bool = False) -> bool:
        """Update user MFA secret and enabled status."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        user.mfa_secret = secret
        user.mfa_enabled = enabled
        
        await self.session.commit()
        return True
    
    async def get_backup_codes(self, user_id: int) -> List[MFABackupCode]:
        """Get all backup codes for a user."""
        result = await self.session.execute(
            select(MFABackupCode).where(
                and_(
                    MFABackupCode.user_id == user_id,
                    MFABackupCode.deleted_at.is_(None)
                )
            )
        )
        return result.scalars().all()
    
    async def save_backup_codes(self, user_id: int, codes: List[str]) -> bool:
        """Save backup codes for a user."""
        backup_codes = []
        for code in codes:
            backup_code = MFABackupCode(
                user_id=user_id,
                code=code,
                used=False
            )
            backup_codes.append(backup_code)
        
        self.session.add_all(backup_codes)
        await self.session.commit()
        return True
    
    async def clear_backup_codes(self, user_id: int) -> bool:
        """Soft delete all backup codes for a user."""
        result = await self.session.execute(
            select(MFABackupCode).where(
                and_(
                    MFABackupCode.user_id == user_id,
                    MFABackupCode.deleted_at.is_(None)
                )
            )
        )
        backup_codes = result.scalars().all()
        
        for backup_code in backup_codes:
            backup_code.deleted_at = datetime.utcnow()
        
        await self.session.commit()
        return True
    
    async def use_backup_code(self, backup_code_id: int) -> bool:
        """Mark a backup code as used."""
        result = await self.session.execute(
            select(MFABackupCode).where(MFABackupCode.id == backup_code_id)
        )
        backup_code = result.scalar_one_or_none()
        
        if not backup_code:
            return False
        
        backup_code.used = True
        backup_code.used_at = datetime.utcnow()
        
        await self.session.commit()
        return True
    
    async def get_mfa_stats(self) -> dict:
        """Get MFA usage statistics."""
        # Total users
        total_users_result = await self.session.execute(
            select(func.count(User.id)).where(
                and_(
                    User.deleted_at.is_(None),
                    User.is_active == True
                )
            )
        )
        total_users = total_users_result.scalar() or 0
        
        # MFA enabled users
        mfa_enabled_result = await self.session.execute(
            select(func.count(User.id)).where(
                and_(
                    User.deleted_at.is_(None),
                    User.is_active == True,
                    User.mfa_enabled == True
                )
            )
        )
        mfa_enabled_users = mfa_enabled_result.scalar() or 0
        
        return {
            "total_users": total_users,
            "mfa_enabled_users": mfa_enabled_users
        }
