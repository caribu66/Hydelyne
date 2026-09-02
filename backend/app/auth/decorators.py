from __future__ import annotations

import hmac
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Optional, TypeVar

from fastapi import Request
from strawberry.types import Info

from app.models import CrewMember
from app.services.crew import auth_service

# Decorators wrap resolver methods of shape (self, info, *args, **kwargs) -> T.
# Precisely typing that shape needs ParamSpec + Concatenate, but the whole
# point of Concatenate here would be to describe a two-fixed-positional-arg
# prefix, which it cannot express alongside an unbounded *args tail from
# Strawberry's generated resolver signatures. TypeVar-bound-to-Callable is
# the standard mypy-recommended fallback for this: it keeps the *decorated*
# function's signature exact at every call site (return type F, not Any),
# while the wrapper body is internally permissive.
F = TypeVar("F", bound=Callable[..., Awaitable[object]])

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication required"):
        self.message = message
        super().__init__(self.message)


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        self.message = message
        super().__init__(self.message)


def require_auth(func: F) -> F:
    """Decorator to require authentication for a resolver."""

    @wraps(func)
    async def wrapper(self: object, info: Info, *args: object, **kwargs: object) -> object:
        request = info.context.get("request")
        if not request:
            from graphql import GraphQLError

            raise GraphQLError("No request context", extensions={"code": "UNAUTHENTICATED"})
        token = _extract_token(request)
        if not token:
            from graphql import GraphQLError

            raise GraphQLError("Authentication required", extensions={"code": "UNAUTHENTICATED"})

        user = await auth_service.get_user_from_token(token)
        if not user:
            from graphql import GraphQLError

            raise GraphQLError("Invalid or expired token", extensions={"code": "UNAUTHENTICATED"})

        info.context["current_user"] = user
        return await func(self, info, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_admin(func: F) -> F:
    """Decorator to require admin role for a resolver."""

    @wraps(func)
    async def wrapper(self: object, info: Info, *args: object, **kwargs: object) -> object:
        request = info.context.get("request")
        if not request:
            from graphql import GraphQLError

            raise GraphQLError("No request context", extensions={"code": "UNAUTHENTICATED"})

        token = _extract_token(request)
        if not token:
            from graphql import GraphQLError

            raise GraphQLError("Authentication required", extensions={"code": "UNAUTHENTICATED"})

        user = await auth_service.get_user_from_token(token)
        if not user:
            from graphql import GraphQLError

            raise GraphQLError("Invalid or expired token", extensions={"code": "UNAUTHENTICATED"})

        # Enforce admin role
        role = getattr(user, "role", "user") or "user"
        if role != "admin":
            from graphql import GraphQLError

            raise GraphQLError(
                "Admin access required",
                extensions={"code": "FORBIDDEN"},
            )

        info.context["current_user"] = user
        return await func(self, info, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


# ---- REST (FastAPI) auth dependencies ----


async def get_current_user_rest(request: Request) -> CrewMember:
    """FastAPI dependency to enforce auth on REST endpoints."""
    from fastapi import HTTPException as _HTTPException

    token = _extract_token(request)
    if not token:
        raise _HTTPException(status_code=401, detail="Authentication required")
    user = await auth_service.get_user_from_token(token)
    if not user:
        raise _HTTPException(status_code=401, detail="Invalid or expired token")
    return user


async def require_admin_rest(request: Request) -> CrewMember:
    """FastAPI dependency to require the admin role on REST endpoints."""
    from fastapi import HTTPException as _HTTPException

    user = await get_current_user_rest(request)
    role = getattr(user, "role", "user") or "user"
    if role != "admin":
        raise _HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_api_key(request: Request) -> bool:
    """FastAPI dependency to require a valid API key for agent access."""
    from fastapi import HTTPException as _HTTPException

    from app.config import get_settings

    settings = get_settings()
    if not settings.API_KEY:
        raise _HTTPException(status_code=503, detail="API key not configured")

    api_key = request.headers.get("X-API-Key", "")
    if not api_key or not hmac.compare_digest(api_key, settings.API_KEY):
        raise _HTTPException(status_code=401, detail="Invalid or missing API key")

    return True


async def require_rest_auth(request: Request) -> CrewMember:
    """Alias for Depends — returns user or raises 401."""
    return await get_current_user_rest(request)


def _extract_token(request: Request) -> Optional[str]:
    """Extract authentication token from request."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    from app.config import get_settings as _gs

    cookie_name = _gs().SESSION_COOKIE_NAME
    token = request.cookies.get(cookie_name)
    if token:
        return token
    # Fallback for legacy cookie name
    token = request.cookies.get("session")
    if token:
        return token

    return None
