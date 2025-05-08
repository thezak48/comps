FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

LABEL maintainer="thezak48" \
    org.opencontainers.image.created=$BUILD_DATE \
    org.opencontainers.image.url="https://github.com/thezak48/comps" \
    org.opencontainers.image.source="https://github.com/thezak48/comps" \
    org.opencontainers.image.version=$VERSION \
    org.opencontainers.image.revision=$VCS_REF \
    org.opencontainers.image.vendor="thezak48" \
    org.opencontainers.image.title="comps" \
    org.opencontainers.image.description="Comps is a open source self hostable version of Slowpoke Pics"

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
COPY /docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Set default environment variables
ENV PUID=1000
ENV PGID=1000
ENV DB_PATH=/config/comparisons.db
ENV UPLOADS_PATH=/data/uploads
ENV RETENTION_DAYS=7

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]
