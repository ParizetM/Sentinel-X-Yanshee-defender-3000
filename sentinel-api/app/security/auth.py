"""Sécurité et Authentification (KAN-36)."""

from typing import Optional
from fastapi import Header, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

security_bearer = HTTPBearer(auto_error=False)


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> str:
    """Vérifie la présence et la validité du token API (Bearer ou Header X-API-Key)."""
    token = None
    if credentials:
        token = credentials.credentials
    elif x_api_key:
        token = x_api_key

    if not token or token != settings.API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton d'authentification manquant ou invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token
