"""Update schema to include total_columns"""
from db import backend_name

def upgrade(cursor):
    # Add total_columns column to comparisons table
    cursor.execute('''
        ALTER TABLE comparisons 
        ADD COLUMN total_columns INTEGER DEFAULT 2
    ''')
    
    # Update existing rows to have total_columns = images_per_row
    cursor.execute('''
        UPDATE comparisons 
        SET total_columns = images_per_row 
        WHERE total_columns IS NULL
    ''')
    
    # Drop the old images_per_row column (SQLite-only path). In Postgres we keep the extra column.
    if backend_name() == 'sqlite':
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
        
        cursor.execute('''
            INSERT INTO comparisons_new 
            SELECT id, name, show_name, total_rows, total_columns, created_at 
            FROM comparisons
        ''')
        
        cursor.execute('DROP TABLE comparisons')
        cursor.execute('ALTER TABLE comparisons_new RENAME TO comparisons')

def downgrade(cursor):
    # Add back images_per_row column
    cursor.execute('''
        ALTER TABLE comparisons 
        ADD COLUMN images_per_row INTEGER DEFAULT 1
    ''')
    
    # Copy total_columns to images_per_row
    cursor.execute('''
        UPDATE comparisons 
        SET images_per_row = total_columns 
        WHERE images_per_row IS NULL
    ''')
    
    # Drop total_columns
    cursor.execute('''
        CREATE TABLE comparisons_new (
            id TEXT PRIMARY KEY,
            name TEXT,
            show_name TEXT,
            total_rows INTEGER DEFAULT 1,
            images_per_row INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        INSERT INTO comparisons_new 
        SELECT id, name, show_name, total_rows, images_per_row, created_at 
        FROM comparisons
    ''')
    
    cursor.execute('DROP TABLE comparisons')
    cursor.execute('ALTER TABLE comparisons_new RENAME TO comparisons')
