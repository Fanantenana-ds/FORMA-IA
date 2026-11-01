"""Shared ownership column for company-scoped business records."""
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID


class TenantOwned:
    """Marks a business record as belonging to a director's company."""

    owner_id = Column(UUID(as_uuid=True), nullable=True, index=True)
