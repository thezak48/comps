def upgrade(conn):
    """
    Add position column to image_metadata table for maintaining upload order
    """
    # Check if position column already exists
    result = conn.execute("PRAGMA table_info(image_metadata)")
    columns = [col[1] for col in result.fetchall()]
    
    # Only add the column if it doesn't exist
    if 'position' not in columns:
        conn.execute('''
            ALTER TABLE image_metadata
            ADD COLUMN position INTEGER
        ''')
    
    # Create an index on the position column for better query performance
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_image_metadata_position 
        ON image_metadata(position)
    ''')

def downgrade(conn):
    """
    Remove position column from image_metadata table
    """
    # Drop the index first
    conn.execute('DROP INDEX IF EXISTS idx_image_metadata_position')
    
    # Remove the position column
    # Note: SQLite doesn't support dropping columns directly, 
    # so we'd need to recreate the table to remove a column
    
    # Get the current table structure
    result = conn.execute("PRAGMA table_info(image_metadata)")
    columns = [col[1] for col in result.fetchall() if col[1] != 'position']
    columns_str = ', '.join(columns)
    
    # Create new table without position column
    conn.execute(f'''
        CREATE TABLE image_metadata_new (
            {columns_str}
        )
    ''')
    
    # Copy data to new table
    conn.execute(f'''
        INSERT INTO image_metadata_new
        SELECT {columns_str}
        FROM image_metadata
    ''')
    
    # Drop old table and rename new one
    conn.execute('DROP TABLE image_metadata')
    conn.execute('ALTER TABLE image_metadata_new RENAME TO image_metadata')
