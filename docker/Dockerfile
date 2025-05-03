FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app user and group
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash appuser

# Create necessary directories
RUN mkdir -p /app/uploads /app/static /config /data
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create volume mount points
VOLUME ["/config", "/data"]

# Copy entrypoint script
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Set default environment variables
ENV PUID=1000
ENV PGID=1000
ENV DB_PATH=/config/comparisons.db
ENV UPLOADS_PATH=/data/uploads

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]
