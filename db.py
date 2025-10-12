import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Lazy imports inside functions to avoid hard dependency if not used


def _is_postgres() -> bool:
    url = os.getenv("DATABASE_URL") or os.getenv("DB_URL") or ""
    backend = os.getenv("DB_BACKEND", "").lower()
    return backend == "postgres" or url.startswith("postgresql://") or url.startswith("postgres://")


def _get_sqlite_path() -> str:
    return os.getenv("DB_PATH", "comparisons.db")


def autoincrement_pk_sql() -> str:
    """Return backend-appropriate SQL for an auto-incrementing primary key column.

    Example usage: f"id {autoincrement_pk_sql()}"
    """
    if _is_postgres():
        return "SERIAL PRIMARY KEY"
    else:
        return "INTEGER PRIMARY KEY AUTOINCREMENT"


def bool_default(value: bool) -> str:
    """Return backend-appropriate DEFAULT for boolean columns."""
    if _is_postgres():
        return "DEFAULT TRUE" if value else "DEFAULT FALSE"
    else:
        return "DEFAULT 1" if value else "DEFAULT 0"


def _convert_placeholders(sql: str) -> str:
    """Convert SQLite-style '?' placeholders to backend-specific ones.

    - SQLite: '?' (no change)
    - Postgres (psycopg): '%s'
    """
    if _is_postgres():
        # Replace each '?' with '%s'. We assume '?' only used for placeholders in our SQL.
        return sql.replace("?", "%s")
    return sql


@contextmanager
def connect(dict_rows: bool = False):
    """Context manager yielding a DB connection and cursor.

    Args:
        dict_rows: If True, rows are returned as dict-like mappings when supported.
    Yields:
        (conn, cursor)
    """
    if _is_postgres():
        dsn = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
        if not dsn:
            raise RuntimeError(
                (
                    "DATABASE_URL/DB_URL not set for Postgres backend. "
                    "Set DB_BACKEND=sqlite to use SQLite."
                )
            )
        # Determine driver once (do not catch exceptions thrown from with-body)
        driver = None
        try:
            import psycopg  # type: ignore
            from psycopg.rows import dict_row  # type: ignore

            driver = ("psycopg3", psycopg, dict_row)
        except Exception:
            try:
                import psycopg2  # type: ignore
                from psycopg2.extras import RealDictCursor  # type: ignore

                driver = ("psycopg2", psycopg2, RealDictCursor)
            except Exception:
                raise

        name, mod, helper = driver
        if name == "psycopg3":
            # helper is dict_row
            if dict_rows:
                conn = mod.connect(dsn, row_factory=helper)
            else:
                conn = mod.connect(dsn)
            try:
                yield conn, conn.cursor()
            finally:
                conn.close()
        else:
            # psycopg2 path; helper is RealDictCursor
            conn = mod.connect(dsn)
            cur = conn.cursor(cursor_factory=helper) if dict_rows else conn.cursor()
            try:
                yield conn, cur
            finally:
                conn.close()
    else:
        import sqlite3

        path = _get_sqlite_path()
        conn = sqlite3.connect(path)
        try:
            if dict_rows:
                conn.row_factory = sqlite3.Row
            yield conn, conn.cursor()
        finally:
            conn.close()


def execute(sql: str, params: Sequence[Any] = ()) -> None:
    sql_conv = _convert_placeholders(sql)
    with connect() as (conn, cur):
        cur.execute(sql_conv, params)
        conn.commit()


def executemany(sql: str, param_list: Iterable[Sequence[Any]]) -> None:
    sql_conv = _convert_placeholders(sql)
    with connect() as (conn, cur):
        cur.executemany(sql_conv, param_list)
        conn.commit()


def execute_with_rowcount(sql: str, params: Sequence[Any] = ()) -> int:
    """Execute a DML statement and return affected rowcount."""
    sql_conv = _convert_placeholders(sql)
    with connect() as (conn, cur):
        cur.execute(sql_conv, params)
        rc = getattr(cur, "rowcount", -1) or 0
        conn.commit()
    return int(rc)


def query(sql: str, params: Sequence[Any] = ()) -> List[Tuple[Any, ...]]:
    sql_conv = _convert_placeholders(sql)
    with connect() as (conn, cur):
        cur.execute(sql_conv, params)
        rows = cur.fetchall()
    return rows


def query_one(sql: str, params: Sequence[Any] = ()) -> Optional[Tuple[Any, ...]]:
    sql_conv = _convert_placeholders(sql)
    with connect() as (conn, cur):
        cur.execute(sql_conv, params)
        row = cur.fetchone()
    return row


def query_dicts(sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    sql_conv = _convert_placeholders(sql)
    with connect(dict_rows=True) as (conn, cur):
        cur.execute(sql_conv, params)
        rows = cur.fetchall()
        # sqlite returns sqlite3.Row which behaves like a mapping; psycopg returns dicts directly
        # Normalize to plain dicts
        result: List[Dict[str, Any]] = []
        for r in rows:
            if isinstance(r, dict):
                result.append({str(k): v for k, v in r.items()})
            elif hasattr(r, "keys"):
                # sqlite3.Row
                keys = list(r.keys())  # type: ignore[call-arg]
                result.append({str(k): r[k] for k in keys})
            else:
                # Fallback: represent as indexed string keys
                try:
                    seq = list(r)
                    result.append({str(i): v for i, v in enumerate(seq)})
                except Exception:
                    result.append({})
    return result


def init_migrations_table_if_needed() -> None:
    """Ensure the migrations table exists with backend-appropriate schema."""
    # Note: Use explicit DDL for PK based on backend
    ddl = f"""
        CREATE TABLE IF NOT EXISTS migrations (
            id {autoincrement_pk_sql()},
            version TEXT NOT NULL,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN {bool_default(False)}
        )
    """
    execute(ddl)


def backend_name() -> str:
    return "postgres" if _is_postgres() else "sqlite"
