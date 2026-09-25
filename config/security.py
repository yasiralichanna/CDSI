"""
CDSI Security Configuration — mTLS, RBAC, JWT Auth.
"""
from __future__ import annotations

import time
from typing import Optional

import jwt
import bcrypt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config.settings import get_settings

security = HTTPBearer(auto_error=False)


class AuthManager:
    """JWT-based authentication and RBAC."""

    ROLES = {
        "admin": ["read", "write", "manage", "rollback", "train"],
        "analyst": ["read", "rollback"],
        "viewer": ["read"],
    }

    @staticmethod
    def create_token(user_id: str, role: str = "viewer") -> str:
        settings = get_settings()
        payload = {
            "sub": user_id,
            "role": role,
            "iat": int(time.time()),
            "exp": int(time.time()) + settings.jwt_expiration_minutes * 60,
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def verify_token(token: str) -> dict:
        settings = get_settings()
        try:
            return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    @classmethod
    def check_permission(cls, role: str, permission: str) -> bool:
        return permission in cls.ROLES.get(role, [])


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> dict:
    """Dependency to get current user from JWT token."""
    if credentials is None:
        # Allow unauthenticated access for now (can be restricted)
        return {"sub": "anonymous", "role": "admin"}
    return AuthManager.verify_token(credentials.credentials)
