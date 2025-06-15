"""User model with password security features."""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlmodel import Field, SQLModel, Relationship, Column, JSON

from .base import BaseModel


class User(BaseModel, SQLModel, table=True):
    """User model with password security features."""
    
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    first_name: str
    last_name: Optional[str] = None
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    
    # Password security fields (Step 1)
    password_changed_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    password_history: List[str] = Field(default=[], sa_column=Column(JSON))
    force_password_change: bool = Field(default=False)
    
    # Account security fields (Step 2)
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = Field(default=None)
    lockout_duration_minutes: int = Field(default=0)
    last_login: Optional[datetime] = Field(default=None)
    
    # MFA fields (Step 3)
    mfa_enabled: bool = Field(default=False)
    mfa_secret: Optional[str] = Field(default=None)
    
    # Relationships
    roles: List["UserRole"] = Relationship(back_populates="user")
    backup_codes: List["MFABackupCode"] = Relationship(back_populates="user")
    
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until
    
    def lock_account(self) -> None:
        """Lock account with progressive duration based on failed attempts."""
        # Progressive lockout: 5min, 15min, 1hour, 24hour
        lockout_durations = [5, 15, 60, 1440]  # minutes
        
        if self.failed_login_attempts >= len(lockout_durations):
            # Maximum lockout (24 hours)
            duration = lockout_durations[-1]
        else:
            duration = lockout_durations[self.failed_login_attempts - 1]
        
        self.lockout_duration_minutes = duration
        self.locked_until = datetime.utcnow() + timedelta(minutes=duration)
    
    def unlock_account(self) -> None:
        """Unlock account and reset failed attempts."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.lockout_duration_minutes = 0
    
    def increment_failed_attempts(self) -> None:
        """Increment failed login attempts and lock if necessary."""
        self.failed_login_attempts += 1
        
        # Lock after 5 failed attempts
        if self.failed_login_attempts >= 5:
            self.lock_account()
    
    def reset_failed_attempts(self) -> None:
        """Reset failed attempts after successful login."""
        self.failed_login_attempts = 0
    
    def add_password_to_history(self, hashed_password: str) -> None:
        """Add password to history, keeping only last 5."""
        if not self.password_history:
            self.password_history = []
        
        self.password_history.append(hashed_password)
        # Keep only last 5 passwords
        if len(self.password_history) > 5:
            self.password_history = self.password_history[-5:]


class Role(BaseModel, SQLModel, table=True):
    """Role model."""
    
    __tablename__ = "roles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    
    # Relationships
    users: List["UserRole"] = Relationship(back_populates="role")


class UserRole(BaseModel, SQLModel, table=True):
    """User-Role association model."""
    
    __tablename__ = "user_roles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    role_id: int = Field(foreign_key="roles.id")
    
    # Relationships
    user: User = Relationship(back_populates="roles")
    role: Role = Relationship(back_populates="users")


class PasswordResetToken(BaseModel, SQLModel, table=True):
    """Password reset token model."""
    
    __tablename__ = "password_reset_tokens"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    used: bool = Field(default=False)
    
    def is_valid(self) -> bool:
        """Check if token is still valid."""
        return not self.used and datetime.utcnow() < self.expires_at


class MFABackupCode(BaseModel, SQLModel, table=True):
    """MFA backup codes model."""
    
    __tablename__ = "mfa_backup_codes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    code: str = Field(index=True)
    used: bool = Field(default=False)
    used_at: Optional[datetime] = Field(default=None)
    
    # Relationships
    user: User = Relationship(back_populates="backup_codes")
