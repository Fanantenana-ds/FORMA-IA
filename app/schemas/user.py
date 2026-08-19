from uuid import UUID
from pydantic import BaseModel, EmailStr
from app.models.user import RoleEnum

class UserCreate(BaseModel):
    nom: str
    email: EmailStr
    password: str
    role: RoleEnum

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id:UUID
    nom: str
    email: EmailStr
    role: RoleEnum

    class Config:
        from_attributes=True