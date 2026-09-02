# ADR 0002: Redis Security Fail-Closed Policy

- Status: accepted
- Date: 2026-09-02
- Owners: backend maintainers
- Supersedes: implicit "all Redis errors fail open" in
  `app/auth/session.py` and `app/middleware.py`

## Context

The backend uses Redis for three classes of behavior:

1. **Token revocation blocklist** — checked by `is_token_revoked(jti)` on every
   authenticated request; controls whether a logged-out session may continue
   to make API calls.
2. **Login brute-force rate limiting** — checked by `RateLimitMiddleware` on
   each request; throttles unauthenticated traffic.
3. **Cache** (`crew_list`, compliance reports, summaries) — best-effort
   performance layer; PostgreSQL is the source of truth.

Historically every Redis-backed control returned a default-on-error (fail-open):
`is_token_revoked` returned `False` on exception; `increment_rate_limit`
returned `None`; cache `get` returned `None`. This means a Redis outage
silently disabled logout, allowed unmetered login attempts, and degraded
cache freshness — with no observability beyond a generic `WARNING`.

A logout that doesn't work is a security hole. An attacker who can knock
over Redis (or wait for it to fall over on its own) extends the life of a
revoked session. Rate limiting that silently fails open during a Redis
incident turns the incident into a brute-force opportunity. Caching is a
different category: it's a performance optimization, not a security control,
and PostgreSQL is the durable store.

## Decision

Per-control failure policy:

| Control | Failure mode | Rationale |
|---|---|---|
| Token revocation (`is_token_revoked`) | **Fail-closed** (treat as revoked) | A failed lookup must not extend the life of a revoked session. |
| `revoke_session_token` (logout write) | **Fail-open at the write site**, log a `security_degradation` event. The cookie is still cleared client-side; the user sees a successful logout, but the server log records that the revocation did not persist. | Refusing the logout is a worse UX than letting the cookie clear, but we must not silently lose the audit signal. |
| Login rate limit + `RateLimitMiddleware` | **Fail-open**, log `security_degradation` | Blocking traffic because Redis is down is an availability event worse than letting unmetered requests through. The incident is observable in logs and metrics. |
| `CacheService.get` / `set` / `delete` | **Fail-open** (existing behavior, unchanged) | Caching is not a security control. |

All branches log a `WARNING` with the marker `security_degradation:` so the
on-call team can alert on the rate. The Redis client is hardened with
`socket_connect_timeout=5`, `socket_timeout=5`, `socket_keepalive=False`,
and `health_check_interval=30` so a hung Redis cannot stall a request thread.

## Alternatives considered

- **Fail-open everywhere (status quo)**: simplest but turns a Redis outage
  into a security incident. Rejected.
- **Fail-closed everywhere**: rate-limit lockout is unacceptable; reject.
- **Circuit breaker around Redis**: deferrable improvement. The current
  fail-open rate-limit code with a security-degradation log is the minimum
  viable observability. A circuit breaker is a follow-up.

## Consequences

- Logout appears successful to the client even if Redis is down; the
  revoked token will not be honored until the next Redis restart, and the
  audit log will show the gap.
- Login rate-limit enforcement becomes a best-effort protection with
  observability; on-call must monitor `security_degradation` log volume.
- The token-revocation lookup has a measurable availability cost: any Redis
  blip logs users out. This is the correct trade-off — better a forced
  re-login than a leaked token.
- Cache behavior is unchanged; performance in degraded mode matches today.

## Migration and rollback

- Forward: edit `app/auth/session.py` and `app/middleware.py`; no schema or
  contract changes. Tests in `tests/test_login_rate_limit.py` and
  `tests/test_auth.py` cover the new behavior.
- Rollback: revert the two files. The default `WARNING` log is unchanged in
  shape, so log dashboards do not break.

## Validation

- `grep "socket_connect_timeout" backend/app/services/cache.py` returns a
  match.
- `pytest tests/test_auth.py -q` passes with the new negative auth tests.
- `pytest tests/test_login_rate_limit.py -q` passes including
  `test_login_rate_limit_not_triggered_when_redis_unavailable`, which
  asserts rate-limit fail-open.
- `grep "security_degradation" backend/app/auth/session.py
  backend/app/middleware.py` returns matches in both files.