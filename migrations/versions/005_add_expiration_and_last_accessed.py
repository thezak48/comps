"""Add last_accessed column and expiration settings to comparisons table"""

def upgrade(cursor):
    # Add last_accessed column to comparisons table
    cursor.execute('''
        ALTER TABLE comparisons 
        ADD COLUMN last_accessed TIMESTAMP
    ''')
    
    # Add expiration_type column to comparisons table
    cursor.execute('''
        ALTER TABLE comparisons 
        ADD COLUMN expiration_type TEXT DEFAULT 'from_last_access'
    ''')
    
    # Add expiration_days column to comparisons table
    cursor.execute('''
        ALTER TABLE comparisons 
        ADD COLUMN expiration_days INTEGER DEFAULT 7
    ''')
    
    # Update existing rows to have default values
    # Set last_accessed = created_at for all existing rows
    cursor.execute('''
        UPDATE comparisons 
        SET last_accessed = created_at 
        WHERE last_accessed IS NULL
    ''')
    
    # Set default expiration values for all existing rows
    cursor.execute('''
        UPDATE comparisons 
        SET expiration_type = 'from_last_access', expiration_days = 7
        WHERE expiration_type IS NULL OR expiration_days IS NULL
    ''')
    
    # Create an index on the last_accessed column for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_comparisons_last_accessed 
        ON comparisons(last_accessed)
    ''')

def downgrade(cursor):
    # Drop the index
    cursor.execute('DROP INDEX IF EXISTS idx_comparisons_last_accessed')
    
    # Create a new table without the expiration columns and last_accessed
    cursor.execute('''
        CREATE TABLE comparisons_new (
            id TEXT PRIMARY KEY,
            name TEXT,
            show_name TEXT,
            total_rows INTEGER DEFAULT 1,
            total_columns INTEGER DEFAULT 2,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Copy data from old table to new table
    cursor.execute('''
        INSERT INTO comparisons_new 
        SELECT id, name, show_name, total_rows, total_columns, created_at
        FROM comparisons
    ''')
    
    # Drop the old table and rename the new one
    cursor.execute('DROP TABLE comparisons')
    cursor.execute('ALTER TABLE comparisons_new RENAME TO comparisons')
