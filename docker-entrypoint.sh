#!/bin/sh
set -e

# Handle Docker bind mount quirk: if host file doesn't exist,
# Docker creates a directory instead of a file
if [ -d /app/backend/business_data.db ]; then
    echo "Removing directory placeholder for database..."
    rm -rf /app/backend/business_data.db
fi

# Initialize database if it doesn't exist
if [ ! -f /app/backend/business_data.db ]; then
    echo "Initializing database..."
    cd /app/backend && python -c "from db import init_db; init_db()"
fi

exec "$@"
