"""Forward the authenticated tenant's JWT during IA → Backend calls.

Business requests entering an IA router already validate their Bearer token.
Keep that token request-local so backend_sync reads and writes stay in the
same tenant as the signed-in user instead of falling back to a service
account with a separate tenant.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextvars import ContextVar, Token
import secrets

from fastapi import Request

from app.utils.security import SHARED_INTERNAL_TOKEN

_request_auth_token: ContextVar[str | None] = ContextVar(
    "formaia_backend_request_auth_token", default=None
)


def get_request_auth_token() -> str | None:
    """Return the validated user JWT bound to the current IA request."""
    return _request_auth_token.get()


async def bind_backend_auth_token(request: Request) -> AsyncGenerator[None, None]:
    """Bind a user JWT for the lifetime of a router request.

    Router authentication dependencies run before this dependency. Internal
    shared tokens are deliberately excluded: they do not identify a tenant.
    """
    authorization = request.headers.get("authorization", "")
    scheme, separator, credential = authorization.partition(" ")
    token: str | None = None
    if (
        separator
        and scheme.lower() == "bearer"
        and credential
        and not secrets.compare_digest(credential, SHARED_INTERNAL_TOKEN)
    ):
        token = credential

    context_token: Token[str | None] = _request_auth_token.set(token)
    try:
        yield
    finally:
        _request_auth_token.reset(context_token)
