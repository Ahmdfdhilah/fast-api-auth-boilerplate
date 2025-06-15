"""Session management using Redis with device tracking."""

import json
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging
from src.core.redis import redis_set, redis_get, redis_delete, redis_exists, redis_get_pattern, redis_flush_pattern
from src.core.config import settings

logger = logging.getLogger(__name__)


class DeviceSessionManager:
    """Manage user sessions in Redis with device tracking and concurrent session limiting."""
    
    def __init__(self, prefix: str = "session", max_sessions_per_user: int = 5):
        self.prefix = prefix
        self.max_sessions_per_user = max_sessions_per_user
        self.default_expire = settings.SESSION_EXPIRE_MINUTES * 60  # Convert minutes to seconds
    
    def _session_key(self, session_id: str) -> str:
        """Generate session key."""
        return f"{self.prefix}:{session_id}"
    
    def _user_sessions_key(self, user_id: int) -> str:
        """Generate user sessions key."""
        return f"{self.prefix}:user:{user_id}"
    
    def _device_sessions_key(self, user_id: int, device_fingerprint: str) -> str:
        """Generate device sessions key."""
        return f"{self.prefix}:device:{user_id}:{device_fingerprint}"
    
    def _create_device_fingerprint(self, user_agent: str, ip_address: str, additional_data: Optional[Dict] = None) -> str:
        """Create device fingerprint from user agent, IP and additional data."""
        fingerprint_data = {
            "user_agent": user_agent,
            "ip_address": ip_address,
            **(additional_data or {})
        }
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]
    
    async def create_session(self, user_id: int, user_agent: str, ip_address: str, 
                           data: Optional[Dict[str, Any]] = None, expire: Optional[int] = None,
                           additional_device_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new session with device tracking."""
        session_id = str(uuid.uuid4())
        expire_time = expire or self.default_expire
        device_fingerprint = self._create_device_fingerprint(user_agent, ip_address, additional_device_data)
        
        # Check and enforce session limits
        await self._enforce_session_limits(user_id)
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "device_fingerprint": device_fingerprint,
            "user_agent": user_agent,
            "ip_address": ip_address,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        
        session_key = self._session_key(session_id)
        success = await redis_set(session_key, session_data, expire_time)
        
        if success:
            # Track session for user and device
            await self._add_user_session(user_id, session_id)
            await self._add_device_session(user_id, device_fingerprint, session_id)
            logger.info(f"Created session {session_id} for user {user_id} on device {device_fingerprint}")
            return {
                "session_id": session_id,
                "device_fingerprint": device_fingerprint,
                "expires_at": (datetime.utcnow() + timedelta(seconds=expire_time)).isoformat()
            }
        
        raise Exception("Failed to create session")
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        session_key = self._session_key(session_id)
        session_data = await redis_get(session_key)
        
        if session_data:
            # Update last activity
            session_data["last_activity"] = datetime.utcnow().isoformat()
            await redis_set(session_key, session_data, self.default_expire)
        
        return session_data
    
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False
        
        session_data["data"].update(data)
        session_data["last_activity"] = datetime.utcnow().isoformat()
        
        session_key = self._session_key(session_id)
        return await redis_set(session_key, session_data, self.default_expire)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_data = await self.get_session(session_id)
        if session_data:
            user_id = session_data["user_id"]
            await self._remove_user_session(user_id, session_id)
        
        session_key = self._session_key(session_id)
        result = await redis_delete(session_key)
        
        if result:
            logger.info(f"Deleted session {session_id}")
        
        return result
    
    async def delete_user_sessions(self, user_id: int) -> int:
        """Delete all sessions for a user (logout from all devices)."""
        sessions = await self.get_user_sessions(user_id)
        deleted_count = 0
        
        for session_id in sessions:
            if await self.delete_session(session_id):
                deleted_count += 1
        
        # Clear user sessions tracking
        user_sessions_key = self._user_sessions_key(user_id)
        await redis_delete(user_sessions_key)
        
        # Clear all device sessions for user
        await self._clear_user_device_sessions(user_id)
        
        logger.info(f"Deleted {deleted_count} sessions for user {user_id}")
        return deleted_count
    
    async def revoke_session(self, session_id: str, reason: str = "manual_revocation") -> bool:
        """Revoke a specific session with reason."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False
        
        # Add revocation info
        session_data["revoked_at"] = datetime.utcnow().isoformat()
        session_data["revocation_reason"] = reason
        session_data["status"] = "revoked"
        
        session_key = self._session_key(session_id)
        await redis_set(session_key, session_data, 60)  # Keep revoked session info for 1 minute
        
        # Remove from active sessions
        user_id = session_data["user_id"]
        device_fingerprint = session_data.get("device_fingerprint")
        
        await self._remove_user_session(user_id, session_id)
        if device_fingerprint:
            await self._remove_device_session(user_id, device_fingerprint, session_id)
        
        logger.info(f"Revoked session {session_id} for user {user_id}, reason: {reason}")
        return True
    
    async def get_user_session_details(self, user_id: int) -> List[Dict[str, Any]]:
        """Get detailed information about all user sessions."""
        sessions = await self.get_user_sessions(user_id)
        session_details = []
        
        for session_id in sessions:
            session_data = await self.get_session(session_id)
            if session_data:
                session_details.append({
                    "session_id": session_id,
                    "device_fingerprint": session_data.get("device_fingerprint"),
                    "user_agent": session_data.get("user_agent"),
                    "ip_address": session_data.get("ip_address"),
                    "created_at": session_data.get("created_at"),
                    "last_activity": session_data.get("last_activity"),
                    "status": session_data.get("status", "active")
                })
        
        return session_details
    
    async def delete_device_sessions(self, user_id: int, device_fingerprint: str) -> int:
        """Delete all sessions for a specific device."""
        device_sessions = await self.get_device_sessions(user_id, device_fingerprint)
        deleted_count = 0
        
        for session_id in device_sessions:
            if await self.delete_session(session_id):
                deleted_count += 1
        
        # Clear device sessions tracking
        device_sessions_key = self._device_sessions_key(user_id, device_fingerprint)
        await redis_delete(device_sessions_key)
        
        logger.info(f"Deleted {deleted_count} sessions for user {user_id} device {device_fingerprint}")
        return deleted_count
    
    async def get_user_sessions(self, user_id: int) -> list:
        """Get all session IDs for a user."""
        user_sessions_key = self._user_sessions_key(user_id)
        sessions = await redis_get(user_sessions_key)
        return sessions or []
    
    async def _add_user_session(self, user_id: int, session_id: str) -> None:
        """Add session to user's session list."""
        sessions = await self.get_user_sessions(user_id)
        if session_id not in sessions:
            sessions.append(session_id)
            user_sessions_key = self._user_sessions_key(user_id)
            await redis_set(user_sessions_key, sessions, self.default_expire * 2)
    
    async def _remove_user_session(self, user_id: int, session_id: str) -> None:
        """Remove session from user's session list."""
        sessions = await self.get_user_sessions(user_id)
        if session_id in sessions:
            sessions.remove(session_id)
            user_sessions_key = self._user_sessions_key(user_id)
            if sessions:
                await redis_set(user_sessions_key, sessions, self.default_expire * 2)
            else:
                await redis_delete(user_sessions_key)
    
    async def _add_device_session(self, user_id: int, device_fingerprint: str, session_id: str) -> None:
        """Add session to device's session list."""
        device_sessions = await self.get_device_sessions(user_id, device_fingerprint)
        if session_id not in device_sessions:
            device_sessions.append(session_id)
            device_sessions_key = self._device_sessions_key(user_id, device_fingerprint)
            await redis_set(device_sessions_key, device_sessions, self.default_expire * 2)
    
    async def _remove_device_session(self, user_id: int, device_fingerprint: str, session_id: str) -> None:
        """Remove session from device's session list."""
        device_sessions = await self.get_device_sessions(user_id, device_fingerprint)
        if session_id in device_sessions:
            device_sessions.remove(session_id)
            device_sessions_key = self._device_sessions_key(user_id, device_fingerprint)
            if device_sessions:
                await redis_set(device_sessions_key, device_sessions, self.default_expire * 2)
            else:
                await redis_delete(device_sessions_key)
    
    async def get_device_sessions(self, user_id: int, device_fingerprint: str) -> list:
        """Get all session IDs for a specific device."""
        device_sessions_key = self._device_sessions_key(user_id, device_fingerprint)
        sessions = await redis_get(device_sessions_key)
        return sessions or []
    
    async def _enforce_session_limits(self, user_id: int) -> None:
        """Enforce concurrent session limits by removing oldest sessions."""
        sessions = await self.get_user_sessions(user_id)
        
        if len(sessions) >= self.max_sessions_per_user:
            # Get session details with timestamps
            session_details = []
            for session_id in sessions:
                session_data = await self.get_session(session_id)
                if session_data:
                    session_details.append({
                        "session_id": session_id,
                        "last_activity": session_data.get("last_activity"),
                        "created_at": session_data.get("created_at")
                    })
            
            # Sort by last activity (oldest first)
            session_details.sort(key=lambda x: x.get("last_activity", x.get("created_at", "")))
            
            # Delete oldest sessions to make room
            sessions_to_delete = len(sessions) - self.max_sessions_per_user + 1
            for i in range(sessions_to_delete):
                if i < len(session_details):
                    await self.revoke_session(session_details[i]["session_id"], "session_limit_exceeded")
    
    async def _clear_user_device_sessions(self, user_id: int) -> None:
        """Clear all device session tracking for a user."""
        pattern = f"{self.prefix}:device:{user_id}:*"
        await redis_flush_pattern(pattern)
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (run periodically)."""
        from src.core.redis import redis_get_pattern
        
        pattern = f"{self.prefix}:*"
        session_keys = await redis_get_pattern(pattern)
        
        cleaned_count = 0
        for key in session_keys:
            # Skip user session tracking keys
            if ":user:" in key:
                continue
            
            session_data = await redis_get(key)
            if not session_data:
                cleaned_count += 1
                continue
            
            # Check if session is too old (more than 7 days of inactivity)
            try:
                last_activity = datetime.fromisoformat(session_data["last_activity"])
                if datetime.utcnow() - last_activity > timedelta(days=7):
                    session_id = key.split(":")[-1]
                    await self.delete_session(session_id)
                    cleaned_count += 1
            except (KeyError, ValueError):
                # Invalid session data, delete it
                await redis_delete(key)
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
        
        return cleaned_count
    
    async def is_session_valid(self, session_id: str, expected_device_fingerprint: Optional[str] = None) -> bool:
        """Validate session and optionally check device fingerprint."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False
        
        # Check if session is revoked
        if session_data.get("status") == "revoked":
            return False
        
        # Check device fingerprint if provided
        if expected_device_fingerprint and session_data.get("device_fingerprint") != expected_device_fingerprint:
            logger.warning(f"Device fingerprint mismatch for session {session_id}")
            return False
        
        return True
    
    async def update_session_activity(self, session_id: str, ip_address: Optional[str] = None) -> bool:
        """Update session last activity and optionally track IP changes."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False
        
        session_data["last_activity"] = datetime.utcnow().isoformat()
        
        # Track IP changes
        if ip_address and session_data.get("ip_address") != ip_address:
            session_data["ip_history"] = session_data.get("ip_history", [])
            session_data["ip_history"].append({
                "ip": session_data.get("ip_address"),
                "changed_at": datetime.utcnow().isoformat()
            })
            session_data["ip_address"] = ip_address
        
        session_key = self._session_key(session_id)
        return await redis_set(session_key, session_data, self.default_expire)


# Global session manager instance
device_session_manager = DeviceSessionManager(max_sessions_per_user=settings.MAX_SESSIONS_PER_USER)

# Backward compatibility
session_manager = device_session_manager
