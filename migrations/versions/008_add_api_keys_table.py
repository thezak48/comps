"""Add api_keys table for user-specific API authentication.

Revision ID: 008
Revises: 007
Create Date: 2025-07-13 18:30:00

"""

# revision identifiers, used by the migration system
revision = '008'
down_revision = '007_add_super_admin_role'

def upgrade(cursor):
    """Create the api_keys table and its indexes."""
    try:
        cursor.execute("""
            CREATE TABLE api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_name TEXT NOT NULL,
                key_prefix TEXT NOT NULL UNIQUE,
                hashed_key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX idx_api_keys_user_id ON api_keys(user_id)")
        cursor.execute("CREATE UNIQUE INDEX idx_api_keys_key_prefix ON api_keys(key_prefix)")
        print("Created api_keys table.")
    except Exception as e:
        print(f"Could not create api_keys table, it might already exist: {e}")

def downgrade(cursor):
    """Remove the api_keys table."""
    try:
        cursor.execute("DROP TABLE api_keys")
        print("Dropped api_keys table.")
    except Exception as e:
        print(f"Could not drop api_keys table, it might not exist: {e}")