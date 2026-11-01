import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base
from app.models.tenant import TenantOwned


class PublicRegistrationLink(TenantOwned, Base):
    __tablename__ = "public_registration_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(96), unique=True, nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True)
    assessment_questions = Column(JSONB, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    date_creation = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class PublicAssessmentAttempt(TenantOwned, Base):
    """Private, per-visitor question set for a public participant link."""

    __tablename__ = "public_assessment_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(96), unique=True, nullable=False)
    link_id = Column(UUID(as_uuid=True), ForeignKey("public_registration_links.id", ondelete="CASCADE"), nullable=False)
    questions = Column(JSONB, nullable=False)
    date_creation = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    submitted_at = Column(DateTime(timezone=True), nullable=True)
