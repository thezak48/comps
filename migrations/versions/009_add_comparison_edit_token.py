"""Add an edit token hash to comparisons for authorizing anonymous writes

Revision ID: 009
Revises: 008
Create Date: 2026-08-16 12:00:00

"""

# revision identifiers, used by the migration system
revision = '009'
down_revision = '008_add_api_keys_table'

from db import backend_name

def upgrade(cursor):
    """Add the edit token columns to the comparisons table.

    edit_token_expires_at holds a Unix timestamp rather than a TIMESTAMP so the
    expiry check does not depend on how each backend interprets CURRENT_TIMESTAMP.
    """
    if backend_name() == "postgres":
        cursor.execute(
            """
            ALTER TABLE comparisons
            ADD COLUMN IF NOT EXISTS edit_token_hash TEXT
            """
        )
        cursor.execute(
            """
            ALTER TABLE comparisons
            ADD COLUMN IF NOT EXISTS edit_token_expires_at BIGINT
            """
        )
    else:
        # SQLite: check the schema first so a re-run does not raise.
        cursor.execute("PRAGMA table_info(comparisons)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'edit_token_hash' not in cols:
            cursor.execute("ALTER TABLE comparisons ADD COLUMN edit_token_hash TEXT")
        if 'edit_token_expires_at' not in cols:
            cursor.execute("ALTER TABLE comparisons ADD COLUMN edit_token_expires_at INTEGER")

def downgrade(_cursor):
    """No-op downgrade.

    SQLite cannot drop a column without recreating the table, which is
    intentionally skipped here.
    """
