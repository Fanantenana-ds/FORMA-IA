"""Small, authenticated profile-photo storage separated from user listings."""
from sqlalchemy import Column, ForeignKey, LargeBinary
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

from app.database import Base


class UserProfilePhoto(Base):
    __tablename__ = "user_profile_photos"

    user_id = Column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    contenu = Column(LargeBinary, nullable=False)
