#!/bin/bash
set -e

echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] Starting application..."


exec "$@"
