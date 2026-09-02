from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

serializer = URLSafeTimedSerializer(settings.SESSION_SECRET_KEY)
MAX_SESSION_AGE = settings.SESSION_MAX_AGE


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 (260k iterations)."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
    return f"pbkdf2_sha256$260000${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against its hash. Supports legacy sha256$ and new pbkdf2 format."""
    try:
        # New format: pbkdf2_sha256$260000$salt$hash
        if stored_hash.startswith("pbkdf2_sha256$"):
            _, iter_str, salt, pw_hash = stored_hash.split("$", 3)
            iterations = int(iter_str)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
            return hmac.compare_digest(dk.hex(), pw_hash)
        # Legacy format: salt$sha256
        salt, pw_hash = stored_hash.split("$", 1)
        attempt = hashlib.sha256((password + salt).encode()).hexdigest()
        return hmac.compare_digest(attempt, pw_hash)
    except (ValueError, AttributeError):
        return False


def create_session_token(user_id: str) -> str:
    """Create a signed session token with a unique token id (jti)."""
    token_id = secrets.token_hex(16)
    payload = {"user_id": user_id, "jti": token_id}
    return serializer.dumps(payload)


def verify_session_token(token: str) -> Optional[tuple[str, Optional[str]]]:
    """Verify a session token's signature and expiry.

    Returns ``(user_id, jti)`` on success, or ``None`` on failure.
    Does NOT check the Redis revocation blocklist — callers should do that
    via :func:`is_token_revoked`.
    """
    try:
        data = serializer.loads(token, max_age=MAX_SESSION_AGE)
        return data.get("user_id"), data.get("jti")
    except (SignatureExpired, BadSignature):
        return None


async def is_token_revoked(jti: Optional[str]) -> bool:
    """Check whether a token id has been revoked in Redis.

    Fail-closed: if Redis is unreachable or errors, the token is treated as
    revoked. Logging out a compromised session must never silently succeed
    because the revocation store is down. See ADR-0002.
    """
    if not jti:
        return False
    try:
        from app.services.cache import cache_service

        key = f"session_revoked:{jti}"
        return await cache_service.get(key) is not None
    except Exception as e:
        logger.warning("security_degradation: revocation lookup failed, failing closed: %s", e)
        return True


async def revoke_session_token(token: str) -> bool:
    """Add a token's jti to the Redis revocation blocklist.

    Called by the logout mutation to make stateless itsdangerous
    tokens revocable server-side. If Redis is unreachable the revocation is
    not persisted; the caller should surface this to the client (the cookie
    is still cleared locally) and we log a security event.
    """
    try:
        from datetime import timedelta

        from app.services.cache import cache_service

        data = serializer.loads(token, max_age=MAX_SESSION_AGE)
        jti = data.get("jti")
        if not jti:
            return False
        key = f"session_revoked:{jti}"
        # Expire the blocklist entry at the token's natural expiry
        return await cache_service.set(key, "revoked", ttl=timedelta(seconds=MAX_SESSION_AGE))
    except Exception as e:
        logger.warning("security_degradation: revoke_session_token failed: %s", e)
        return False
