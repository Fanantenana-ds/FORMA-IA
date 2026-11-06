from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import RoleEnum


class UserCreate(BaseModel):
    nom: str
    email: EmailStr
    password: str
    role: RoleEnum


class UserUpdate(BaseModel):
    """Mise à jour partielle d'un utilisateur (tous les champs sont optionnels)."""
    nom: str | None = None
    email: EmailStr | None = None
    role: RoleEnum | None = None
    actif: bool | None = None


class UserProfileUpdate(BaseModel):
    """Champs que l'utilisateur peut mettre à jour sur son propre compte."""
    nom: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = None


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
