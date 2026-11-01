"""Request-local tenant identity used by ORM and file registries."""
from contextvars import ContextVar
from uuid import UUID

_tenant_id: ContextVar[UUID | None] = ContextVar("formaia_tenant_id", default=None)


def set_tenant_id(value: UUID | str | None) -> None:
    if value is None:
        _tenant_id.set(None)
    else:
        _tenant_id.set(value if isinstance(value, UUID) else UUID(str(value)))


def get_tenant_id() -> UUID | None:
    return _tenant_id.get()
