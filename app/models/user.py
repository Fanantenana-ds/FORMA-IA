from uuid import uuid4

from enum import Enum

from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SQlEnum

from app.database import Base

class RoleEnum(str, Enum):
    DIRECTION = "Direction"
    ASSISTANT = "Assistant"
    COMPTABLE = "Comptable"
    FORMATEUR = "Formateur"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True),default=uuid4, primary_key=True, index=True)
    nom = Column(String(50), nullable=False)
    email = Column(String(50), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    role = Column(SQlEnum(RoleEnum, name="role_enum"), nullable=False)
    actif = Column(Boolean, default=True)