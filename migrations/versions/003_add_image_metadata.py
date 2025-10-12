"""Add image metadata table"""
from db import autoincrement_pk_sql

def upgrade(cursor):
    # Create image_metadata table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS image_metadata (
            id {autoincrement_pk_sql()},
            comparison_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT,
            image_size TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (comparison_id) REFERENCES comparisons (id)
        )
    ''')
    
    # Create indices
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_image_metadata_comparison 
        ON image_metadata(comparison_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_image_metadata_filename 
        ON image_metadata(filename)
    ''')

def downgrade(cursor):
    # Drop indices first
    cursor.execute('DROP INDEX IF EXISTS idx_image_metadata_comparison')
    cursor.execute('DROP INDEX IF EXISTS idx_image_metadata_filename')
    
    # Drop the table
    cursor.execute('DROP TABLE IF EXISTS image_metadata')
