"""Authorization and permission checking."""

from typing import List, Dict, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import verify_token
from src.core.database import get_db
from src.repositories.user import UserRepository


class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(
            JWTBearer, self
        ).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid authentication scheme.",
                )
            return credentials.credentials
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authorization code.",
            )


jwt_bearer = JWTBearer()


async def get_current_user(
    token: str = Depends(jwt_bearer), 
    session: AsyncSession = Depends(get_db)
) -> Dict:
    """Get the current authenticated user from the token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception

        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(int(user_id))

        if not user:
            raise credentials_exception

        # Get user roles
        user_roles = await user_repo.get_user_roles(user.id)
        roles = [role.name for role in user_roles]

        user_data = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "name": f"{user.first_name} {user.last_name or ''}".strip(),
            "roles": roles,
            "is_active": user.is_active,
        }

        return user_data

    except JWTError:
        raise credentials_exception
    except ValueError:
        raise credentials_exception


async def get_current_active_user(
    current_user: Dict = Depends(get_current_user),
) -> Dict:
    """Check if the current user is active."""
    if not current_user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Inactive user"
        )
    return current_user


def require_roles(required_roles: List[str]):
    """Decorator to require specific roles."""
    async def _check_roles(
        current_user: Dict = Depends(get_current_active_user),
    ) -> Dict:
        user_roles = current_user.get("roles", [])
        
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {', '.join(required_roles)}",
            )
        
        return current_user
    
    return _check_roles


# Common role dependencies
admin_required = require_roles(["admin"])
user_required = require_roles(["user", "admin"])
