"""Add user authentication with invitation codes

Revision ID: 006
Revises: 005_add_expiration_and_last_accessed
Create Date: 2023-05-01 12:00:00

"""

# revision identifiers, used by Alembic
revision = '006'
down_revision = '005_add_expiration_and_last_accessed'

import os
import logging
from db import autoincrement_pk_sql, bool_default, backend_name

def upgrade(cursor):
    """Add user authentication tables and fields"""
    
    # Create users table
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS users (
        id {autoincrement_pk_sql()},
        username TEXT UNIQUE NOT NULL,
        invitation_code_hash TEXT NOT NULL,
        is_admin BOOLEAN {bool_default(False)},
        never_expire_comparisons BOOLEAN {bool_default(False)},
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create invitation_codes table
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS invitation_codes (
        id {autoincrement_pk_sql()},
        code TEXT UNIQUE NOT NULL,
        created_by INTEGER,
        is_used BOOLEAN {bool_default(False)},
        used_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users (id),
        FOREIGN KEY (used_by) REFERENCES users (id)
    )
    ''')
    
    # Add user_id to comparisons table (idempotent across backends)
    if backend_name() == "postgres":
        cursor.execute(
            """
            ALTER TABLE comparisons
            ADD COLUMN IF NOT EXISTS user_id INTEGER
            """
        )
    else:
        # SQLite: check schema to avoid exceptions on re-run
        cursor.execute("PRAGMA table_info(comparisons)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'user_id' not in cols:
            cursor.execute(
                """
                ALTER TABLE comparisons ADD COLUMN user_id INTEGER
                """
            )

    # Add never_expire flag to comparisons table (use backend-safe boolean default)
    if backend_name() == "postgres":
        cursor.execute(
            f"""
            ALTER TABLE comparisons
            ADD COLUMN IF NOT EXISTS never_expire BOOLEAN {bool_default(False)}
            """
        )
    else:
        # SQLite: check schema to avoid exceptions on re-run
        cursor.execute("PRAGMA table_info(comparisons)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'never_expire' not in cols:
            cursor.execute(
                f"""
                ALTER TABLE comparisons ADD COLUMN never_expire BOOLEAN {bool_default(False)}
                """
            )
    
    # Create indices for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_invitation_codes_code ON invitation_codes(code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comparisons_user_id ON comparisons(user_id)')
    
    # Create first admin user with a predefined invitation code
    import hashlib
    # Get admin code from environment variable or use default (for initial setup only)
    admin_code = os.getenv("ADMIN_INVITATION_CODE", "admin-setup-123456")
    # Log a warning if using the default admin code
    if admin_code == "admin-setup-123456":
        logging.warning("WARNING: Using default admin invitation code. This is insecure!")
        logging.warning("Set the ADMIN_INVITATION_CODE environment variable to a secure value.")
    admin_code_hash = hashlib.sha256(admin_code.encode()).hexdigest()
    
    # Ensure admin user exists (idempotent)
    cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
    row = cursor.fetchone()
    if row:
        admin_id = row[0]
    else:
        cursor.execute(
            'INSERT INTO users (username, invitation_code_hash, is_admin, never_expire_comparisons) VALUES (?, ?, ?, ?)',
            ('admin', admin_code_hash, True, True)
        )
        cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
        admin_id = cursor.fetchone()[0]

    # Ensure the invitation code exists (idempotent)
    cursor.execute('SELECT id FROM invitation_codes WHERE code = ?', (admin_code,))
    ic_row = cursor.fetchone()
    if not ic_row:
        cursor.execute(
            'INSERT INTO invitation_codes (code, created_by) VALUES (?, ?)',
            (admin_code, admin_id)
        )

    # Mark the admin's invitation code as used
    cursor.execute(
        'UPDATE invitation_codes SET is_used = ?, used_by = ? WHERE code = ?',
        (True, admin_id, admin_code)
    )

def downgrade(cursor):
    """Remove user authentication tables and fields"""
    
    # Remove columns from comparisons table
    # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
    
    # First, get the current schema
    cursor.execute("PRAGMA table_info(comparisons)")
    columns = cursor.fetchall()
    
    # Create a new table without the user_id and never_expire columns
    column_defs = []
    column_names = []
    for col in columns:
        if col[1] not in ['user_id', 'never_expire']:
            column_defs.append(f"{col[1]} {col[2]}")
            column_names.append(col[1])
    
    cursor.execute(f'''
    CREATE TABLE comparisons_temp (
        {', '.join(column_defs)}
    )
    ''')
    
    # Copy data to the new table
    cursor.execute(f'''
    INSERT INTO comparisons_temp ({', '.join(column_names)})
    SELECT {', '.join(column_names)} FROM comparisons
    ''')
    
    # Drop the old table and rename the new one
    cursor.execute('DROP TABLE comparisons')
    cursor.execute('ALTER TABLE comparisons_temp RENAME TO comparisons')
    
    # Drop the user authentication tables
    cursor.execute('DROP TABLE IF EXISTS invitation_codes')
    cursor.execute('DROP TABLE IF EXISTS users')
