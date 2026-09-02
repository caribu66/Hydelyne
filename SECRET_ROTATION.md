# Secret Rotation Guide

## Overview

This document describes the secrets used by Hydenlyne Crew DMS and the
impact of rotating each one.  In production, always rotate secrets one at a
time and verify service health after each rotation.

## Secrets

### SESSION_SECRET_KEY (Auth tokens)

- **What it protects**: itsdangerous-signed session token (login cookie).
- **Rotation impact**: **All existing sessions are invalidated.** Users must
  re-authenticate.  New tokens will use the new key; old tokens cannot be
  verified.
- **Mitigation**: The Redis-backed JTI revocation blocklist
  (`session_revoked:<jti>`) allows explicit logout revocation without
  changing the key.  However, a key rotation makes all *old* tokens
  unreadable (signature mismatch), so a hard logout-all occurs.
- **How to rotate**:
  1. Update `SESSION_SECRET_KEY` in the secret manager / `.env`.
  2. Restart the backend service.
  3. All users are logged out; instruct them to re-authenticate.

### REDIS_PASSWORD

- **What it protects**: Redis (rate limiting, session revocation blocklist,
  Celery broker).
- **Rotation impact**: Redis rejects all unauthenticated connections.  The
  rate limiter and session revocation list are temporarily unavailable until
  the backend/Celery workers pick up the new password.
- **How to rotate**:
  1. Update `REDIS_PASSWORD` in `.env`.
  2. Update the `redis` service command in `docker-compose.yml` (or
     `docker-compose.prod.yml`).
  3. Restart Redis, then restart backend + workers.

### MEILI_MASTER_KEY

- **What it protects**: Meilisearch search index/master access.
- **Rotation impact**: Search API calls fail until the new key is propagated.
- **How to rotate**:
  1. Generate a new key.
  2. Update `MEILI_MASTER_KEY` in `.env`.
  3. Restart the Meilisearch container with the new key (requires data re-index).

### POSTGRES_PASSWORD

- **What it protects**: PostgreSQL database.
- **Rotation impact**: **Breaking** — database connections drop.  Existing
  PostgreSQL users with hashed passwords are unaffected, but the `hydenlyne`
  login user's password must be updated via `ALTER USER`.
- **How to rotate**:
  1. `ALTER USER hydenlyne WITH PASSWORD '<new_password>';`
  2. Update `POSTGRES_PASSWORD` and `DATABASE_URL` in `.env`.
  3. Restart all services.

### API_KEY

- **What it protects**: Agent-to-backend REST API access.
- **Rotation impact**: Existing agents using the old key receive `401`.
- **How to rotate**:
  1. Generate a new key.
  2. Update `API_KEY` in `.env`.
  3. Restart backend.
  4. Distribute the new key to all agents.

### DROPBOX_REFRESH_TOKEN

- **What it protects**: Dropbox API access (file uploads/downloads).
- **Rotation impact**: Dropbox file operations fail until a new refresh token
  is provisioned.  With `REQUIRE_DROPBOX_STORAGE=true` document uploads are
  rejected rather than stored locally, so treat this as user-facing downtime.
- **Lifetime**: Does not expire on a clock.  It stops working only if revoked
  in the Dropbox app console, or if the app's key/secret is regenerated.
- **How to rotate**: Run `python backend/dropbox_authorize.py`, authorise in
  the browser, paste the printed `DROPBOX_REFRESH_TOKEN` into `backend/.env`,
  and restart backend + workers.  Revoke the old token in the app console.

### DROPBOX_ACCESS_TOKEN (legacy)

- **Status**: Superseded by `DROPBOX_REFRESH_TOKEN`.  Only read when no
  refresh token is configured.
- **Why not to use it**: Dropbox no longer issues long-lived access tokens.
  A console-generated `sl.` token expires after roughly four hours, after
  which every Dropbox call returns `expired_access_token` until someone
  edits `.env` by hand and restarts.  Leave blank once a refresh token is set.

## Session Revocation (P1 hardening)

The application now supports server-side session revocation via a Redis
blocklist.  When `logout` is called, the token's `jti` (unique token ID)
is added to `session_revoked:<jti>` in Redis with an expiry equal to the
token's remaining lifetime.  Subsequent `verify_session_token` calls check
this blocklist and reject revoked tokens.

- **Session max age**: reduced from 24h to 8h in production
  (`SESSION_MAX_AGE=28800`).
- **Revocation granularity**: per-token (jti-level), not per-user.
- **Redis unavailability**: revocation is best-effort; if Redis is down,
  tokens are accepted based on signature + expiry only (no revocation check).
