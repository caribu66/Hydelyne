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
MAX_LOGIN_EMAIL_LENGTH = 320
MAX_LOGIN_PASSWORD_LENGTH = 1024
MAX_PASSWORD_HASH_ITERATIONS = 1_000_000


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
            if not 1 <= iterations <= MAX_PASSWORD_HASH_ITERATIONS:
                return False
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
            return hmac.compare_digest(dk.hex(), pw_hash)
        # Legacy format: salt$sha256
        salt, pw_hash = stored_hash.split("$", 1)
        attempt = hashlib.sha256((password + salt).encode()).hexdigest()
        return hmac.compare_digest(attempt, pw_hash)
    except (ValueError, AttributeError):
        return False


# Perform the same expensive verification work for unknown accounts as for a
# real account, preventing login timing from revealing whether an email exists.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def create_session_token(user_id: str) -> str:
    """Create a signed session token with a unique token id (jti)."""
    token_id = secrets.token_hex(16)
    payload = {"user_id": user_id, "jti": token_id}
    return serializer.dumps(payload)


def verify_session_token(token: str) -> Optional[tuple[str, str]]:
    """Verify a session token's signature and expiry.

    Returns ``(user_id, jti)`` on success, or ``None`` on failure. Both
    identifiers are required; accepting a signed legacy payload without a
    jti would create a session that can never be revoked.
    Does NOT check the Redis revocation blocklist — callers should do that
    via :func:`is_token_revoked`.
    """
    try:
        data = serializer.loads(token, max_age=MAX_SESSION_AGE)
        if not isinstance(data, dict):
            return None
        user_id = data.get("user_id")
        jti = data.get("jti")
        if (
            not isinstance(user_id, str)
            or not user_id.strip()
            or not isinstance(jti, str)
            or not jti.strip()
        ):
            return None
        return user_id, jti
    except (SignatureExpired, BadSignature, TypeError, AttributeError):
        return None


async def is_token_revoked(jti: Optional[str]) -> bool:
    """Check whether a token id has been revoked in Redis.

    Fail-closed: if Redis is unreachable or errors, the token is treated as
    revoked. Logging out a compromised session must never silently succeed
    because the revocation store is down. See ADR-0002.
    """
    if not isinstance(jti, str) or not jti.strip():
        # A session without a revocation identifier is not safely revocable.
        # Reject it rather than turning a malformed/legacy token into a
        # permanent authenticated session.
        return True
    try:
        from app.services.cache import cache_service

        if not await cache_service.is_redis_available():
            logger.warning(
                "security_degradation: revocation lookup failed, failing closed: redis unavailable"
            )
            return True

        key = f"session_revoked:{jti}"
        redis = await cache_service._get_redis()
        return await redis.get(key) is not None
    except Exception as e:
        logger.warning(
            "security_degradation: revocation lookup failed, failing closed: %s",
            type(e).__name__,
        )
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
        logger.warning("security_degradation: revoke_session_token failed: %s", type(e).__name__)
        return False
