#!/bin/bash
set -e

echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] Starting application..."

# Run database migrations
echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] Running database migrations..."
python -m alembic upgrade head

echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] Migrations completed successfully"

exec "$@"
