#!/bin/bash
set -e

echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] Starting application..."

if [ "${RUN_STORAGE_MIGRATION}" = "true" ]; then
  MIGRATION_ENV="${MIGRATION_ENV:-production}"
  STORAGE_MIGRATION_LIMIT="${STORAGE_MIGRATION_LIMIT:-500}"
  STORAGE_MIGRATION_START_AFTER_ID="${STORAGE_MIGRATION_START_AFTER_ID:-0}"

  if [ -n "${STORAGE_MIGRATION_TYPES}" ]; then
    python migrate.py --env "${MIGRATION_ENV}" storage-migrate --execute --limit "${STORAGE_MIGRATION_LIMIT}" --start-after-id "${STORAGE_MIGRATION_START_AFTER_ID}" --types "${STORAGE_MIGRATION_TYPES}"
  else
    python migrate.py --env "${MIGRATION_ENV}" storage-migrate --execute --limit "${STORAGE_MIGRATION_LIMIT}" --start-after-id "${STORAGE_MIGRATION_START_AFTER_ID}"
  fi
fi
exec "$@"
