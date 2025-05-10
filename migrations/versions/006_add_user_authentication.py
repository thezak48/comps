"""Add user authentication with invitation codes

Revision ID: 006
Revises: 005_add_expiration_and_last_accessed
Create Date: 2023-05-01 12:00:00

"""

# revision identifiers, used by Alembic
revision = '006'
down_revision = '005_add_expiration_and_last_accessed'

from datetime import datetime
import sqlite3
import os
import logging

def upgrade(cursor):
    """Add user authentication tables and fields"""
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        invitation_code_hash TEXT NOT NULL,
        is_admin BOOLEAN DEFAULT 0,
        never_expire_comparisons BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create invitation_codes table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS invitation_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        created_by INTEGER,
        is_used BOOLEAN DEFAULT 0,
        used_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users (id),
        FOREIGN KEY (used_by) REFERENCES users (id)
    )
    ''')
    
    # Add user_id to comparisons table
    cursor.execute('''
    ALTER TABLE comparisons ADD COLUMN user_id INTEGER
    ''')
    
    # Add never_expire flag to comparisons table
    cursor.execute('''
    ALTER TABLE comparisons ADD COLUMN never_expire BOOLEAN DEFAULT 0
    ''')
    
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
    
    cursor.execute(
        'INSERT INTO users (username, invitation_code_hash, is_admin, never_expire_comparisons) VALUES (?, ?, ?, ?)',
        ('admin', admin_code_hash, 1, 1)
    )
    
    # Get the admin user ID
    cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
    admin_id = cursor.fetchone()[0]
    
    # Create the first invitation code
    cursor.execute(
        'INSERT INTO invitation_codes (code, created_by) VALUES (?, ?)',
        (admin_code, admin_id)
    )
    
    # Mark the admin's invitation code as used
    cursor.execute(
        'UPDATE invitation_codes SET is_used = 1, used_by = ? WHERE code = ?',
        (admin_id, admin_code)
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
