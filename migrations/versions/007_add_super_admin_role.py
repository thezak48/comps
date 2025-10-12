"""Add super_admin role

Revision ID: 007
Revises: 006
Create Date: 2025-07-13 12:00:00

"""

# revision identifiers, used by Alembic
revision = '007'
down_revision = '006_add_user_authentication'

from db import bool_default, backend_name

def upgrade(cursor):
    """Add is_super_admin column and set the first admin as super admin"""
    # Add is_super_admin column to users table (idempotent per backend)
    if backend_name() == "postgres":
        cursor.execute(
            f"""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN {bool_default(False)}
            """
        )
    else:
        # SQLite: check current schema first to avoid exception on re-run
        cursor.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'is_super_admin' not in cols:
            cursor.execute(
                f"""
                ALTER TABLE users ADD COLUMN is_super_admin BOOLEAN {bool_default(False)}
                """
            )

    # Make the first user a super admin (use boolean value, not integer)
    cursor.execute('UPDATE users SET is_super_admin = ? WHERE id = ?', (True, 1))


def downgrade(_cursor):
    """No-op downgrade.

    SQLite doesn't easily support dropping columns. A true downgrade would
    require table recreation, which we intentionally skip here.
    """