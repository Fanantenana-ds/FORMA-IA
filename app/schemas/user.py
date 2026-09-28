from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr
from app.models.user import RoleEnum


class UserCreate(BaseModel):
    nom: str
    email: EmailStr
    password: str
    role: RoleEnum


class UserUpdate(BaseModel):
    """Mise à jour partielle d'un utilisateur (tous les champs sont optionnels)."""
    nom: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[RoleEnum] = None
    actif: Optional[bool] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    nom: str
    email: str
    role: RoleEnum

    class Config:
        from_attributes = True


class UserAdminResponse(BaseModel):
    """Réponse enrichie pour la DIRECTION (inclut le statut actif/inactif)."""
    id: UUID
    nom: str
    email: str
    role: RoleEnum
    actif: bool

    class Config:
        from_attributes = True