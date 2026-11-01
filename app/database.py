from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session as OrmSession, declarative_base, sessionmaker, with_loader_criteria

from app.config.settings import settings
from app.core.tenant_context import get_tenant_id

# ============================================================
# DATABASE ENGINE
# ============================================================

engine = create_engine(
    settings.DATABASE_URL
)


# ============================================================
# SESSION
# ============================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ============================================================
# BASE
# ============================================================

Base = declarative_base()


@event.listens_for(OrmSession, "do_orm_execute")
def _scope_tenant_reads(execute_state):
    """Automatically scope ORM reads to the authenticated director's company."""
    if not (execute_state.is_select or execute_state.is_update or execute_state.is_delete):
        return
    tenant_id = execute_state.session.info.get("tenant_owner_id") or get_tenant_id()
    if tenant_id is None:
        return
    from app.models.tenant import TenantOwned

    statement = execute_state.statement
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if issubclass(model, TenantOwned):
            statement = statement.options(
                with_loader_criteria(
                    model,
                    model.owner_id == tenant_id,
                    include_aliases=True,
                )
            )
    execute_state.statement = statement


@event.listens_for(OrmSession, "before_flush")
def _assign_tenant_on_insert(session, _flush_context, _instances):
    """Attach newly-created business records to the authenticated tenant."""
    tenant_id = session.info.get("tenant_owner_id") or get_tenant_id()
    if tenant_id is None:
        return
    from app.models.tenant import TenantOwned

    for instance in session.new:
        if isinstance(instance, TenantOwned) and instance.owner_id is None:
            instance.owner_id = tenant_id


# ============================================================
# DEPENDENCY DATABASE
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
