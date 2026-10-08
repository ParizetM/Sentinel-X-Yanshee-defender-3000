"""Routeur d'authentification (Contrat §4.4 & KAN-36)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication (Contrat §4.4)"])


class LoginRequest(BaseModel):
    username: str = Field(..., examples=["admin"])
    password: str = Field(..., examples=["Epsi1234.!"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Connexion et obtention du jeton (Contrat §4.4)",
    description="Authentifie un opérateur ou un service et délivre le jeton API."
)
async def login(credentials: LoginRequest):
    # Identifiants de l'équipe (validés pour la soutenance et le labo)
    valid_users = {
        "admin": "Epsi1234.!",
        "supervisor": "Sentinel2026!",
        "martin": "Sentinel2026!"
    }

    if credentials.username in valid_users and valid_users[credentials.username] == credentials.password:
        return {
            "access_token": settings.API_SECRET_KEY,
            "token_type": "bearer",
            "role": "admin" if credentials.username == "admin" else "supervisor"
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants incorrects"
    )
