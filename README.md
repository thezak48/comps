# Comps

[![Build Status](https://github.com/thezak48/comps/actions/workflows/docker-build.yml/badge.svg)](https://github.com/thezak48/comps/actions/workflows/docker-build.yml)
[![Docker Image Version](https://img.shields.io/docker/v/thezak48/comps?sort=semver)](https://hub.docker.com/r/thezak48/comps)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/thezak48/comps/blob/develop/LICENSE)
[![Security Status](https://github.com/thezak48/comps/workflows/security/badge.svg)](https://github.com/thezak48/comps/security/advisories)

Comps is a open source self hostable version of Slowpoke Pics. A web-based tool for comparing multiple images side by side.

Tots not vibe coded because lazy

## Features

- Upload multiple images for side-by-side comparison
- Navigate between images using keyboard shortcuts or UI controls
- Add metadata like comparison name, show name, and tags
- Fit-to-screen and original size viewing modes
- Border toggle for better image separation
- Responsive design for different screen sizes
- Docker support for easy deployment

## Installation

### Using Docker (Recommended)

1. Clone the repository:

## API Documentation

Comps provides a RESTful API for programmatic access:

For more details, see the [API Documentation](https://thezak48.github.io/comps/).

## Database backends

Comps supports both SQLite (default) and PostgreSQL.

- SQLite (default): set DB_PATH to the SQLite file path (default: comparisons.db)
- PostgreSQL: set DB_BACKEND=postgres and provide DATABASE_URL (or DB_URL) like:
	- postgresql://user:pass@host:5432/dbname

Migrations run automatically at startup for the selected backend.

## Storage backends

Comps supports local filesystem storage (default) and S3-compatible object storage.

- Local (default): `STORAGE_BACKEND=local` and `UPLOADS_PATH` (default: `uploads`)
- S3: set `STORAGE_BACKEND=s3` and:
    - `S3_BUCKET_NAME=<bucket>`
    - `S3_REGION=<region>` (optional, but recommended)
    - `S3_ENDPOINT_URL=<endpoint>` (optional, for S3-compatible providers like MinIO)
    - `S3_KEY_PREFIX=<prefix>` (optional)
    - `S3_PUBLIC_BASE_URL=<public-domain>` (optional, use when the bucket is publicly served through a custom domain/CDN)
    - `S3_PRESIGNED_URL_TTL_SECONDS=<seconds>` (optional, default: `3600`)
    - `S3_PRESIGNED_URL_CACHE_MAX_SIZE=<entries>` (optional, default: `10000`; `0` disables the cache)

Presigned URLs are reused in a bounded, thread-safe, per-process cache and refreshed five seconds before their configured expiry. Uploads and deletes invalidate the affected comparison/image entries, including concurrent lookups. The effective URL TTL is limited to 1–604800 seconds. Temporary S3 credentials can expire sooner; use a suitably short TTL or disable the cache when credential lifetimes are shorter than the configured TTL.

This keeps redirect targets stable so browsers can reuse cached image responses. Image freshness is still controlled by the object's/CDN's `Cache-Control` policy; Comps does not configure that policy or purge CDN/browser caches. The app's redirects themselves are not cached, so they cannot retain expired signed destinations.

When S3 storage and `S3_PUBLIC_BASE_URL` are both enabled, Comps embeds direct public image URLs in comparison pages and skips signing for `/uploads/...` redirects. Local storage ignores this setting. The base must be an absolute HTTP(S) URL without credentials, a query, or a fragment; an optional base path is supported. Object keys are URL-encoded.

Example: Cloudflare R2 with a public custom domain

```bash
STORAGE_BACKEND=s3
S3_BUCKET_NAME=comps-images
S3_REGION=auto
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_PUBLIC_BASE_URL=https://images.example.com
S3_KEY_PREFIX=comps
```

Use your normal S3-compatible credentials for uploads and deletes. The browser-facing image URLs come from the public domain, while the app still uses the S3 API endpoint for storage operations. This option requires an already-public bucket/CDN and does not change bucket permissions; do not enable it for images intended to remain private.

For canvas-based features such as solarization, configure the public domain to send CORS headers for your Comps origin, for example:

```http
Access-Control-Allow-Origin: https://comp.example.com
```

If multiple sites use the public asset domain, configure the specific origins you trust rather than using `*`.

### Migrating existing local uploads to S3

If you are switching an existing installation from local storage to S3, run:

```bash
python scripts/migrate_local_uploads_to_s3.py --skip-existing
```

This script uploads files from `UPLOADS_PATH` to your configured S3 bucket/key prefix and updates `image_metadata.image_size` (inserting metadata rows when missing).
For AWS S3 you can optionally add `--expected-bucket-owner <account-id>` for ownership verification.

### Docker Compose example (PostgreSQL)

Use the provided `docker-compose.postgres.yml`:

```bash
docker compose -f docker-compose.postgres.yml up -d --build
```

This spins up Postgres and the app with `DB_BACKEND=postgres` and `DATABASE_URL` set, waits for Postgres to be healthy, then starts the app. The app’s entrypoint blocks until migrations initialize.

## Testing

Install the application and development dependencies, then run the Python suite:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

Run with branch coverage:

```bash
python -m pytest --cov --cov-report=term-missing
```

Tests use isolated SQLite databases and upload directories under `.pytest-tmp`; they do not use the configured production database or storage. Static assets are checked separately with `npm run check`.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

### Third-Party Code

This project includes code from EasyCompare (Copyright (C) 2020 N3xusHD, Sec-ant) licensed under GPL-3.0.
