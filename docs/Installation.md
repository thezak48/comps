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
- `S3_PRESIGNED_URL_TTL_SECONDS=<seconds>` (optional, default `3600`)

To migrate existing local uploads into S3 after switching storage backend:

```bash
python scripts/migrate_local_uploads_to_s3.py --skip-existing
```

For AWS S3 you can optionally add `--expected-bucket-owner <account-id>`.
