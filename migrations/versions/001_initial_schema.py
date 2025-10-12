"""Initial database schema migration"""
from datetime import datetime
from db import autoincrement_pk_sql, bool_default

def upgrade(cursor):
    # Create migrations version table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS migrations (
            id {autoincrement_pk_sql()},
            version TEXT NOT NULL,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN {bool_default(False)}
        )
    ''')
    
    # Create comparisons table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comparisons (
            id TEXT PRIMARY KEY,
            name TEXT,
            show_name TEXT,
            total_rows INTEGER DEFAULT 1,
            images_per_row INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create tags table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS tags (
            id {autoincrement_pk_sql()},
            comparison_id TEXT,
            tag TEXT,
            FOREIGN KEY (comparison_id) REFERENCES comparisons (id)
        )
    ''')
    
    # Create image_positions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS image_positions (
            comparison_id TEXT,
            filename TEXT,
            row_number INTEGER,
            column_position INTEGER,
            FOREIGN KEY (comparison_id) REFERENCES comparisons (id)
        )
    ''')

def downgrade(cursor):
    # Drop all tables in reverse order
    cursor.execute('DROP TABLE IF EXISTS image_positions')
    cursor.execute('DROP TABLE IF EXISTS tags')
    cursor.execute('DROP TABLE IF EXISTS comparisons')
    cursor.execute('DROP TABLE IF EXISTS migrations')
