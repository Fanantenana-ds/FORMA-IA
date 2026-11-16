"""Progression M1 par tâche ; aucune dépendance HTTP dans l'orchestration."""
from contextvars import ContextVar

PROGRESS_CALLBACK = ContextVar("m1_progress_callback", default=None)


async def emit_progress(event, stage, message, **data):
    callback = PROGRESS_CALLBACK.get()
    if callback is not None:
        await callback(event, {"stage": stage, "message": message, **data})
