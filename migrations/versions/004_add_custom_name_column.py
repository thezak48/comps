"""Add custom_name column to image_metadata table"""

def upgrade(cursor):
    # Add custom_name column to image_metadata table
    cursor.execute('''
        ALTER TABLE image_metadata 
        ADD COLUMN custom_name TEXT
    ''')

def downgrade(cursor):
    # Create a new table without the custom_name column
    from db import autoincrement_pk_sql
    cursor.execute(f'''
        CREATE TABLE image_metadata_backup (
            id {autoincrement_pk_sql()},
            comparison_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT,
            image_size TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (comparison_id) REFERENCES comparisons (id)
        )
    ''')
    
    # Copy data from the original table to the backup table
    cursor.execute('''
        INSERT INTO image_metadata_backup 
        SELECT id, comparison_id, filename, original_filename, image_size, created_at
        FROM image_metadata
    ''')
    
    # Drop the original table
    cursor.execute('DROP TABLE image_metadata')
    
    # Rename the backup table to the original table name
    cursor.execute('ALTER TABLE image_metadata_backup RENAME TO image_metadata')
    
    # Recreate indices
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_image_metadata_comparison 
        ON image_metadata(comparison_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_image_metadata_filename 
        ON image_metadata(filename)
    ''')
