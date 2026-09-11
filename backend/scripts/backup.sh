#!/usr/bin/env bash
set -euo pipefail

# PostgreSQL backup script for Hydenlyne Crew DMS.
# Produces a compressed, timestamped dump of the production database.
#
# Usage:
#   ./backend/scripts/backup.sh
#   BACKUP_DIR=/tmp/backups ./backend/scripts/backup.sh
#
# The script reads DATABASE_URL from the environment (or falls back to the
# docker-compose default).  It is safe to run while the application is live;
# pg_dump uses a REPEATABLE READ transaction and does not block writers.

# Default lives on the persisted document_storage volume
# (/app/data/documents), so dumps survive container recreation in both
# dev and prod — unlike an unmounted /app/backups.
BACKUP_DIR="${BACKUP_DIR:-/app/data/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILENAME="hydenlyne-${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL is not set" >&2
    exit 1
fi

echo "Backing up database -> ${BACKUP_DIR}/${FILENAME}"

# pg_dump (libpq) cannot parse SQLAlchemy async driver schemes such as
# postgresql+asyncpg:// — strip the driver suffix before invoking it.
LIBPQ_URL="${DATABASE_URL/+asyncpg/}"
LIBPQ_URL="${LIBPQ_URL/+psycopg2/}"
pg_dump "${LIBPQ_URL}" --format=plain --no-owner --no-acl \
    | gzip > "${BACKUP_DIR}/${FILENAME}"

echo "Backup complete: ${BACKUP_DIR}/${FILENAME} ($(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1))"

# Retention: keep the 7 most recent dumps. Portable across GNU/BSD:
# nullglob avoids a failing glob when empty, and xargs runs only when
# there is actually something to delete (xargs -r is GNU-only).
shopt -s nullglob
dumps=("${BACKUP_DIR}"/hydenlyne-*.sql.gz)
if ((${#dumps[@]} > 7)); then
    printf '%s\n' "${dumps[@]}" \
        | xargs ls -1t 2>/dev/null \
        | tail -n +8 \
        | xargs rm -f
fi
echo "Retention policy applied (kept 7 most recent)."
