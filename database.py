import os
import shutil
from datetime import datetime, timedelta
from typing import List, Optional

from db import backend_name, execute, query, query_one
from migrations.manager import MigrationManager

DB_PATH = os.getenv("DB_PATH", "comparisons.db")


def init_db():
    """Initialize database and run migrations"""
    migration_manager = MigrationManager()
    migration_manager.migrate(DB_PATH)


def create_comparison(
    comparison_id: str,
    name: Optional[str],
    show_name: Optional[str],
    tags: Optional[List[str]],
    metadata: dict,
    user_id: Optional[int] = None,
):
    # Insert
    never_expire_initial = False
    if metadata.get("never_expire") is not None:
        never_expire_initial = bool(metadata.get("never_expire"))
    execute(
        """
        INSERT INTO comparisons (
            id, name, show_name, total_rows, total_columns,
            expiration_type, expiration_days, never_expire
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            comparison_id,
            name,
            show_name,
            metadata.get("total_rows", 1),
            metadata.get("total_columns", 2),
            metadata.get("expiration_type", "from_last_access"),
            int(metadata.get("expiration_days", 7)),
            never_expire_initial,
        ),
    )

    # Set default expiration based on metadata
    if metadata.get("never_expire") is not None:
        execute(
            "UPDATE comparisons SET never_expire = ? WHERE id = ?",
            (bool(metadata.get("never_expire")), comparison_id),
        )

    # If user is authenticated, associate the comparison with them
    # and set never_expire if applicable
    if user_id is not None:
        execute("UPDATE comparisons SET user_id = ? WHERE id = ?", (user_id, comparison_id))
        row = query_one("SELECT never_expire_comparisons FROM users WHERE id = ?", (user_id,))
        user_never_expire_setting = row
        if user_never_expire_setting and user_never_expire_setting[0]:
            # If the user's setting is to never expire,
            # and the comparison isn't explicitly set to expire
            if metadata.get("never_expire") is None or metadata.get("never_expire") is True:
                execute(
                    "UPDATE comparisons SET never_expire = ? WHERE id = ?",
                    (True, comparison_id),
                )

    if tags:
        for tag in tags:
            execute(
                "INSERT INTO tags (comparison_id, tag) VALUES (?, ?)",
                (comparison_id, tag),
            )


def update_last_accessed(comparison_id: str):
    """Update the last_accessed timestamp for a comparison"""
    # Best-effort update; if column missing on older schema, ignore
    execute(
        "UPDATE comparisons SET last_accessed = CURRENT_TIMESTAMP WHERE id = ?",
        (comparison_id,),
    )


def get_comparison(comparison_id: str):
    rows = query(
        """
        SELECT id, name, show_name, total_rows, total_columns,
               expiration_type, expiration_days, created_at, last_accessed
        FROM comparisons WHERE id = ?
        """,
        (comparison_id,),
    )
    comparison = rows[0] if rows else None

    if comparison:

        def _to_str_dt(v):
            if v is None:
                return None
            if isinstance(v, datetime):
                return v.strftime("%Y-%m-%d %H:%M:%S")
            return str(v)

        tag_rows = query("SELECT tag FROM tags WHERE comparison_id = ?", (comparison_id,))
        tags = [row[0] for row in tag_rows]

        # Get user information if available
        user_info = query_one(
            "SELECT user_id, never_expire FROM comparisons WHERE id = ?",
            (comparison_id,),
        )
        user_id, never_expire = user_info if user_info else (None, 0)

        return {
            "id": comparison[0],
            "name": comparison[1],
            "show_name": comparison[2],
            "tags": tags,
            "total_rows": comparison[3],
            "total_columns": comparison[4],
            "expiration_type": comparison[5] or "from_last_access",
            "expiration_days": comparison[6] or 7,
            "created_at": _to_str_dt(comparison[7]),
            "last_accessed": (_to_str_dt(comparison[8]) if comparison[8] is not None else None),
            "user_id": user_id,
            "never_expire": bool(never_expire),
        }

    return None


def get_user_comparisons(user_id: int) -> List[dict]:
    """Get all comparisons created by a specific user."""
    rows = query(
        (
            "SELECT id, name, show_name, created_at, last_accessed, never_expire "
            "FROM comparisons WHERE user_id = ? ORDER BY last_accessed DESC"
        ),
        (user_id,),
    )

    comparisons = []
    for row in rows:

        def _to_str_dt(v):
            if v is None:
                return None
            if isinstance(v, datetime):
                return v.strftime("%Y-%m-%d %H:%M:%S")
            return str(v)

        comparisons.append(
            {
                "id": row[0],
                "name": row[1],
                "show_name": row[2],
                "created_at": _to_str_dt(row[3]),
                "last_accessed": (_to_str_dt(row[4]) if row[4] is not None else None),
                "never_expire": bool(row[5]),
            }
        )
    return comparisons


def store_image_position(comparison_id: str, filename: str, row_number: int, column_position: int):
    # Emulate SQLite's INSERT OR REPLACE in Postgres by delete + insert
    if backend_name() == "postgres":
        execute(
            (
                "DELETE FROM image_positions WHERE comparison_id = ? AND filename = ? "
                "AND row_number = ? AND column_position = ?"
            ),
            (comparison_id, filename, row_number, column_position),
        )
        execute(
            (
                "INSERT INTO image_positions (comparison_id, filename, row_number, "
                "column_position) VALUES (?, ?, ?, ?)"
            ),
            (comparison_id, filename, row_number, column_position),
        )
    else:
        execute(
            """
            INSERT OR REPLACE INTO image_positions (
                comparison_id, filename, row_number, column_position
            ) VALUES (?, ?, ?, ?)
            """,
            (comparison_id, filename, row_number, column_position),
        )


def store_image_metadata(
    comparison_id: str, filename: str, original_filename: str, image_size: str
):
    """
    Store metadata for an uploaded image

    Args:
        comparison_id: The UUID of the comparison
        filename: The UUID-based filename in the filesystem
        original_filename: The original filename as uploaded by the user
        image_size: The size of the image (formatted string)
    """
    # Store the metadata (table expected from migrations)
    if backend_name() == "postgres":
        # Replace existing row for same (comparison_id, filename)
        execute(
            "DELETE FROM image_metadata WHERE comparison_id = ? AND filename = ?",
            (comparison_id, filename),
        )
        execute(
            (
                "INSERT INTO image_metadata (comparison_id, filename, original_filename, "
                "image_size) VALUES (?, ?, ?, ?)"
            ),
            (comparison_id, filename, original_filename, image_size),
        )
    else:
        execute(
            """
            INSERT OR REPLACE INTO image_metadata (
                comparison_id, filename, original_filename, image_size
            ) VALUES (?, ?, ?, ?)
            """,
            (comparison_id, filename, original_filename, image_size),
        )


def update_image_custom_name(comparison_id: str, filename: str, custom_name: str):
    """
    Update the custom name for an image

    Args:
        comparison_id: The UUID of the comparison
        filename: The UUID-based filename in the filesystem
        custom_name: The custom name provided by the user
    """
    execute(
        "UPDATE image_metadata SET custom_name = ? WHERE comparison_id = ? AND filename = ?",
        (custom_name, comparison_id, filename),
    )


def get_expired_comparisons(retention_days: int):
    """
    Get a list of comparisons that haven't been accessed in more than retention_days

    Args:
        retention_days: Number of days to keep comparisons

    Returns:
        List of comparison IDs that are older than the retention period
    """
    expired_ids = []

    # Get all comparisons with their expiration settings
    comparisons = query(
        (
            """
        SELECT id, expiration_type, expiration_days, created_at,
               last_accessed, never_expire
        FROM comparisons
        """
        )
    )
    print(f"Checking for expired comparisons with retention_days={retention_days}")
    num = len(comparisons)
    print(f"Found {num} comparisons to check for expiration")
    current_time = datetime.now()
    for (
        comp_id,
        exp_type,
        exp_days,
        created_at,
        last_accessed,
        never_expire,
    ) in comparisons:
        # Use comparison's own expiration days if available, otherwise use default
        days = exp_days if exp_days is not None else retention_days
        print(
            f"Checking comparison {comp_id}: type={exp_type}, days={days}, created={created_at}, last_accessed={last_accessed}"  # noqa: E501
        )

        # Check if this comparison is marked as never expire
        if never_expire:
            print(f"  Comparison {comp_id} is marked as never expire, skipping")
            continue

        if exp_type == "from_creation" and created_at:
            # Support both string and datetime types across backends
            created_dt = (
                created_at
                if isinstance(created_at, datetime)
                else datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            )
            cutoff_date = created_dt + timedelta(days=days)
            print(
                f"  From creation: cutoff={cutoff_date}, current={current_time}, expired={current_time > cutoff_date}"  # noqa: E501
            )
            if current_time > cutoff_date:
                expired_ids.append(comp_id)
        elif exp_type == "from_last_access" and last_accessed:
            last_dt = (
                last_accessed
                if isinstance(last_accessed, datetime)
                else datetime.strptime(last_accessed, "%Y-%m-%d %H:%M:%S")
            )
            cutoff_date = last_dt + timedelta(days=days)
            print(
                f"  From last access: cutoff={cutoff_date}, current={current_time}, expired={current_time > cutoff_date}"  # noqa: E501
            )
            if current_time > cutoff_date:
                expired_ids.append(comp_id)
    return expired_ids


def delete_comparison(comparison_id: str, uploads_path: str):
    """
    Delete a comparison and all associated data

    Args:
        comparison_id: The UUID of the comparison to delete
        uploads_path: Path to the uploads directory
    """
    # Delete all related records
    execute("DELETE FROM image_positions WHERE comparison_id = ?", (comparison_id,))
    execute("DELETE FROM image_metadata WHERE comparison_id = ?", (comparison_id,))
    execute("DELETE FROM tags WHERE comparison_id = ?", (comparison_id,))
    execute("DELETE FROM comparisons WHERE id = ?", (comparison_id,))

    # Delete the comparison directory and all files
    comparison_dir = os.path.join(uploads_path, comparison_id)
    if os.path.exists(comparison_dir):
        shutil.rmtree(comparison_dir)
