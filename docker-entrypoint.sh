#!/bin/bash
set -e

# Export environment variables for Python
export PLENTICORE_HOST="${PLENTICORE_HOST:-}"
export PLENTICORE_PASSWORD="${PLENTICORE_PASSWORD:-}"
export PLENTICORE_EXPORTER_PORT="${PLENTICORE_EXPORTER_PORT:-8080}"

if [ -z "$PLENTICORE_HOST" ] || [ -z "$PLENTICORE_PASSWORD" ]; then
    echo "Error: PLENTICORE_HOST and PLENTICORE_PASSWORD must be set" >&2
    exit 1
fi

# Run the exporter with proper signal handling for graceful shutdown
exec python3 "${PYTHONUNBUFFERED:=1}" "$@"
