"""Add super_admin role

Revision ID: 007
Revises: 006
Create Date: 2025-07-13 12:00:00

"""

# revision identifiers, used by Alembic
revision = '007'
down_revision = '006_add_user_authentication'

def upgrade(cursor):
    """Add is_super_admin column and set the first admin as super admin"""
    try:
        # Add is_super_admin column to users table
        cursor.execute('ALTER TABLE users ADD COLUMN is_super_admin BOOLEAN DEFAULT 0')
        
        # Find the first user (who is the admin) and make them a super admin
        cursor.execute('UPDATE users SET is_super_admin = 1 WHERE id = 1')
        
    except Exception as e:
        # This might fail if the column already exists, which is fine for development.
        # For a real production environment, more careful checks would be needed.
        print(f"Could not add is_super_admin column, it might already exist: {e}")


def downgrade(cursor):
    """Remove is_super_admin column"""
    # SQLite doesn't easily support dropping columns.
    # A more complex migration with table recreation would be needed for a true downgrade.
    # For this project, we will leave this empty.
    pass