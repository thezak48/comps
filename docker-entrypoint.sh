#!/bin/bash

# Set user and group based on environment variables
groupmod -o -g "$PGID" appgroup
usermod -o -u "$PUID" appuser

# Create necessary directories if they don't exist
mkdir -p /config /data/uploads
chown -R appuser:appgroup /config /data /app

# Switch to appuser

# Simple readiness check: try to import app (runs migrations), then start uvicorn.
echo "[entrypoint] Waiting for database and migrations to be ready..."
su appuser -c "python - << 'PY'
import os,time,sys
max_wait=60
start=time.time()
while True:
	try:
		import main  # triggers init_db()
		break
	except Exception as e:
		if time.time()-start>max_wait:
			print('[entrypoint] DB/migrations not ready:', e)
			sys.exit(1)
		time.sleep(2)
print('[entrypoint] DB ready.')
PY"

exec su appuser -c "uvicorn main:app --host 0.0.0.0 --port 8000"
