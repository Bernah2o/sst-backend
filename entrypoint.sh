#!/bin/bash
set -e

# Function to log messages with timestamp
log() {
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] $@"
}

log "Starting entrypoint script..."

# Verify environment variables
if [ -z "$DATABASE_URL" ]; then
    log "WARNING: DATABASE_URL is not set. Migrations might fail."
fi

# Run database migrations with error handling
log "Running database migrations..."
if alembic upgrade head; then
    log "Database migrations completed successfully."
else
    log "ERROR: Database migrations failed! Check your database connection and credentials."
    # We don't exit here immediately to allow debugging if needed, 
    # but normally we should exit. Let's exit to fail fast.
    exit 1
fi

log "Starting application..."
if [ ! -z "$APP_VERSION" ]; then
    log "Version: $APP_VERSION"
fi
if [ ! -z "$BUILD_DATE" ]; then
    log "Build Date: $BUILD_DATE"
fi

# Executing the command
log "Executing command: $@"
exec "$@"
