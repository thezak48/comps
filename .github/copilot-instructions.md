## Comps – AI Agent Notes

Big picture
- FastAPI app serving both HTML UI and REST API. Entrypoint `main.py` mounts static/templates, defines HTML routes, custom OpenAPI at `/openapi.json`, and a background cleanup task.
- Versioned API at `/api/v1` in `api/router.py` using Pydantic models from `api/models.py`.
- SQLite via direct `sqlite3` in `database.py` (no ORM). Schema managed by simple migrations in `migrations/`.
- Filesystem uploads in `UPLOADS_PATH` (`uploads/`), served at `/uploads`. Auth supports cookie (web) and Bearer/API key (API) in `auth.py`.

Data flow
- Create comparison -> `database.create_comparison()` inserts into `comparisons` and `tags`.
- Upload image -> save to `uploads/<comparison_id>/<uuid>.<ext>`, then `image_positions` and `image_metadata` are updated.
- Read comparison -> join grid + metadata (see `api/router.get_comparison_detail()` and `main.view_comparison()`).
- Cleanup -> `main.cleanup_old_comparisons()` uses `database.get_expired_comparisons()` then `delete_comparison()`.

Auth
- Web: `session` cookie with JWT (`auth.create_access_token`); routes use `auth.get_optional_user()`.
- API: `POST /api/v1/login` with username + invitation code, then `Authorization: Bearer <jwt>` or a raw `comps_...` API key.
- Admin/super-admin gate `/admin` and management actions (`auth.is_admin`, `auth.is_super_admin`).

DB & migrations
- Migrations in `migrations/versions/NNN_*.py` expose `upgrade(cursor)`; applied by `migrations/manager.py` at startup via `database.init_db()`.
- Pattern: check columns with PRAGMA before use (e.g., `last_accessed`, expiration fields) to tolerate mixed versions.
- When adding fields: create a new migration, update `database.py` and API reads/writes, and keep PRAGMA guards where helpful.

Conventions
- API prefix `/api/v1`; keep models in `api/models.py` aligned with SQL and response shapes.
- Grid limits: API caps `total_rows` at 200; UI dropdown caps at 20.
- Random name generator exists in both `main.py` and `api/router.py`—avoid drift.
- Image size stored as human-readable string (e.g., `"1024 bytes"`).

Run & CI
- Local: `uvicorn main:app --host 0.0.0.0 --port 8000` (Swagger UI page at `/api/docs`).
- Lint/format: `scripts/check_format_lint.(sh|bat)` or `scripts/format_all.(sh|bat)`; JS/CSS via `npm run` scripts in `package.json`.
- Docs: `scripts/generate_openapi.py` then `scripts/generate_swagger_ui.py api_docs/openapi.json`; published by `.github/workflows/publish-docs.yml` to `gh-pages`.
- CI builds/pushes Docker images from root `Dockerfile` (`.github/workflows/docker-build.yml`).

Env & files
- Key env: `DB_PATH`, `UPLOADS_PATH`, `RETENTION_DAYS`, `SECRET_KEY` (JWT), `PUID`/`PGID` (container). Templates in `templates/`, static in `static/`.

Gotchas
- Some deployments may lag migrations—keep PRAGMA guards and write idempotent upgrades.
- Root `docker-compose.yml` references `docker/Dockerfile`, while CI uses root `Dockerfile`—prefer root Dockerfile unless restructuring.
- Stick to `sqlite3` patterns unless explicitly migrating to an ORM.

If any workflow or data shape above is unclear for your change, call it out and I’ll expand this file.
