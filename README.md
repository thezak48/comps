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

### Docker Compose example (PostgreSQL)

Use the provided `docker-compose.postgres.yml`:

```bash
docker compose -f docker-compose.postgres.yml up -d --build
```

This spins up Postgres and the app with `DB_BACKEND=postgres` and `DATABASE_URL` set, waits for Postgres to be healthy, then starts the app. The app’s entrypoint blocks until migrations initialize.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

### Third-Party Code

This project includes code from EasyCompare (Copyright (C) 2020 N3xusHD, Sec-ant) licensed under GPL-3.0.
