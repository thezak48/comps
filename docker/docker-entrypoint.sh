#!/bin/bash

# Set user and group based on environment variables
groupmod -o -g "$PGID" appgroup
usermod -o -u "$PUID" appuser

# Create necessary directories if they don't exist
mkdir -p /config /data/uploads
chown -R appuser:appgroup /config /data /app

# Switch to appuser
exec su appuser -c "uvicorn main:app --host 0.0.0.0 --port 8000"
