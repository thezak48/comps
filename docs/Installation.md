# Installation Guide

### Using Docker (Recommended)

1. Clone the repository:

```bash
git clone https://github.com/thezak48/comps.git
cd image-comparison-tool
```

2. Build and run with Docker Compose:

```bash
cd docker
docker-compose up -d
```

3. Access the application at http://comps:8000

### Manual Installation

1. Clone the repository
2. Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4. Run the application:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```
5. Access the application at http://localhost:8000

## Database configuration

By default, Comps uses SQLite and stores data in `comparisons.db`.

To use PostgreSQL instead:

- Install dependencies: psycopg (included in requirements.txt)
- Set environment variables:
    - `DB_BACKEND=postgres`
    - `DATABASE_URL=postgresql://user:pass@host:5432/dbname`

Migrations are applied automatically at startup.

## Storage configuration

By default, Comps stores images on local disk using `UPLOADS_PATH`.

To use S3-compatible storage:

- `STORAGE_BACKEND=s3`
- `S3_BUCKET_NAME=<bucket-name>`
- `S3_REGION=<region>` (optional, recommended)
- `S3_ENDPOINT_URL=<endpoint-url>` (optional, for MinIO/other compatible services)
- `S3_KEY_PREFIX=<prefix>` (optional)
- `S3_PUBLIC_BASE_URL=<public-domain>` (optional, use when the bucket is publicly served through a custom domain/CDN)
- `S3_PRESIGNED_URL_TTL_SECONDS=<seconds>` (optional, default `3600`)

If `S3_PUBLIC_BASE_URL` is set, Comps will generate direct browser image URLs against that public domain instead of using presigned redirects.

Example: Cloudflare R2 with a public custom domain

```bash
STORAGE_BACKEND=s3
S3_BUCKET_NAME=comps-images
S3_REGION=auto
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_PUBLIC_BASE_URL=https://images.example.com
S3_KEY_PREFIX=comps
```

Use your normal S3-compatible credentials for uploads and deletes. The browser-facing image URLs will come from `S3_PUBLIC_BASE_URL`, while the app still talks to the R2 S3 API endpoint for storage operations.

If you use canvas-based features like solarization, make sure the public domain sends a CORS header similar to:

```http
Access-Control-Allow-Origin: https://comp.example.com
```

If the public asset domain is used from multiple sites, allow only the specific origins you trust rather than using `*`.

To migrate existing local uploads into S3 after switching storage backend:

```bash
python scripts/migrate_local_uploads_to_s3.py --skip-existing
```

For AWS S3 you can optionally add `--expected-bucket-owner <account-id>`.
