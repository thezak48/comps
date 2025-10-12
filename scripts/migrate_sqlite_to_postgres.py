"""
Utility to migrate an existing SQLite database to Postgres.

Usage:
  python scripts/migrate_sqlite_to_postgres.py \
    --sqlite-path comparisons.db \
    --database-url postgresql://user:pass@host:5432/dbname \
    [--wipe-target]

Notes:
 - Ensures Postgres schema is present by running app migrations first.
 - Copies core tables with best-effort boolean conversions.
 - Optionally wipes target tables before inserting to avoid conflicts.
 - Resets SERIAL sequences to max(id) where applicable.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

# Ensure project root is on sys.path so we can import 'database' and 'db' later
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BOOL_COLUMNS = {
    "users": {"is_admin", "never_expire_comparisons", "is_super_admin"},
    "invitation_codes": {"is_used"},
    "comparisons": {"never_expire"},
}


TABLE_ORDER: List[str] = [
    # No FKs dependent on these first
    "users",
    "invitation_codes",
    # Core objects
    "comparisons",
    "tags",
    # Images data
    "image_metadata",
    "image_positions",
    # API keys
    "api_keys",
]


SERIAL_ID_TABLES = [
    "users",
    "invitation_codes",
    "api_keys",
    "image_metadata",
]


def _convert_booleans(tbl: str, row: Dict[str, Any]) -> Dict[str, Any]:
    cols = BOOL_COLUMNS.get(tbl, set())
    for c in cols:
        if c in row:
            row[c] = bool(row[c]) if row[c] is not None else False
    return row


def _get_sqlite_rows(sqlite_path: str, table: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    con = sqlite3.connect(sqlite_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        # pull all rows
        cur.execute(f"SELECT {', '.join(cols)} FROM {table}")
        rows = [dict(r) for r in cur.fetchall()]
        return cols, rows
    finally:
        con.close()


def _wipe_target_tables(execute_fn: Callable[[str, Sequence[Any]], Any]):
    # Delete in dependency-safe order (children first)
    execute_fn("DELETE FROM image_positions", ())
    execute_fn("DELETE FROM image_metadata", ())
    execute_fn("DELETE FROM tags", ())
    execute_fn("DELETE FROM comparisons", ())
    execute_fn("DELETE FROM invitation_codes", ())
    execute_fn("DELETE FROM api_keys", ())
    execute_fn("DELETE FROM users", ())


def _reset_sequences(
    backend_name_fn: Callable[[], str],
    query_one_fn: Callable[[str, Sequence[Any]], Any],
    execute_fn: Callable[[str, Sequence[Any]], Any],
):
    if backend_name_fn() != "postgres":
        return
    # Reset SERIAL sequences when present
    for tbl in SERIAL_ID_TABLES:
        row = query_one_fn("SELECT pg_get_serial_sequence(?, 'id')", (tbl,))
        seq = row[0] if row else None
        if not seq:
            continue
        # seq is like 'public.users_id_seq'
        execute_fn(
            (f"SELECT setval('{seq}', " f"(SELECT COALESCE(MAX(id), 1) FROM {tbl}), true)"),
            (),
        )


def _insert_rows(
    table: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    executemany_fn: Callable[[str, Sequence[Sequence[Any]]], Any],
):
    if not rows:
        return
    # Convert booleans where needed
    rows = [_convert_booleans(table, dict(r)) for r in rows]
    col_list = ", ".join(columns)
    placeholders = ", ".join(["?" for _ in columns])
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    values: List[Sequence[Any]] = []
    for r in rows:
        values.append([r.get(c) for c in columns])
    executemany_fn(sql, values)


def migrate(sqlite_path: str, pg_url: str, wipe_target: bool = False):
    # Point adapter at Postgres and ensure schema
    os.environ["DB_BACKEND"] = "postgres"
    os.environ["DATABASE_URL"] = pg_url
    # Import app modules lazily (after sys.path and env are set) to satisfy flake8 E402
    import database  # type: ignore  # noqa: WPS433
    from db import backend_name as _backend_name  # type: ignore  # noqa: WPS433
    from db import execute as _execute
    from db import executemany as _executemany
    from db import query_one as _query_one

    if _backend_name() != "postgres":
        raise RuntimeError("Failed to configure Postgres backend from DATABASE_URL")

    # Ensure schema is present
    database.init_db()

    if wipe_target:
        _wipe_target_tables(_execute)

    for table in TABLE_ORDER:
        try:
            cols, rows = _get_sqlite_rows(sqlite_path, table)
        except sqlite3.OperationalError:
            # Table might not exist in source; skip gracefully
            continue
        if not rows:
            continue
        _insert_rows(table, cols, rows, _executemany)

    # Reset sequences for SERIAL id tables
    _reset_sequences(_backend_name, _query_one, _execute)


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite DB to Postgres")
    parser.add_argument("--sqlite-path", required=True, help="Path to source SQLite DB file")
    parser.add_argument(
        "--database-url",
        required=True,
        help="Target Postgres connection string (postgresql://user:pass@host:port/db)",
    )
    parser.add_argument(
        "--wipe-target",
        action="store_true",
        help="Delete all target rows before migrating (use with caution)",
    )
    args = parser.parse_args()

    migrate(args.sqlite_path, args.database_url, wipe_target=args.wipe_target)
    print("Migration completed.")


if __name__ == "__main__":
    main()
