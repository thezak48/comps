import sqlite3
import os
from datetime import datetime
from typing import List, Optional
from migrations.manager import MigrationManager

DB_PATH = os.getenv('DB_PATH', 'comparisons.db')

def init_db():
    """Initialize database and run migrations"""
    migration_manager = MigrationManager()
    migration_manager.migrate(DB_PATH)

def create_comparison(comparison_id: str, name: Optional[str], show_name: Optional[str], tags: Optional[List[str]], metadata: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute(
        'INSERT INTO comparisons (id, name, show_name, total_rows, total_columns) VALUES (?, ?, ?, ?, ?)',
        (comparison_id, name, show_name, metadata.get('total_rows', 1), metadata.get('total_columns', 2))
    )
    c.execute('CREATE INDEX IF NOT EXISTS idx_image_positions ON image_positions(comparison_id, row_number, column_position)')
    
    if tags:
        for tag in tags:
            c.execute(
                'INSERT INTO tags (comparison_id, tag) VALUES (?, ?)',
                (comparison_id, tag)
            )
    
    conn.commit()
    conn.close()

def get_comparison(comparison_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('SELECT id, name, show_name, total_rows, total_columns FROM comparisons WHERE id = ?', (comparison_id,))
    comparison = c.fetchone()
    
    if comparison:
        c.execute('SELECT tag FROM tags WHERE comparison_id = ?', (comparison_id,))
        tags = [row[0] for row in c.fetchall()]
        
        return {
            'id': comparison[0],
            'name': comparison[1],
            'show_name': comparison[2],
            'tags': tags,
            'total_rows': comparison[3],
            'total_columns': comparison[4]
        }
    
    return None

def store_image_position(comparison_id: str, filename: str, row_number: int, column_position: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute(
        'INSERT OR REPLACE INTO image_positions (comparison_id, filename, row_number, column_position) VALUES (?, ?, ?, ?)',
        (comparison_id, filename, row_number, column_position)
    )
    
    conn.commit()
    conn.close()

def store_image_metadata(comparison_id: str, filename: str, original_filename: str, image_size: str):
    """
    Store metadata for an uploaded image
    
    Args:
        comparison_id: The UUID of the comparison
        filename: The UUID-based filename in the filesystem
        original_filename: The original filename as uploaded by the user
        image_size: The size of the image (formatted string)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if the table exists (should be created by migrations)
    c.execute('''
        SELECT name FROM sqlite_master WHERE type='table' AND name='image_metadata'
    ''')
    if not c.fetchone():
        # Create table if it doesn't exist (fallback)
        c.execute('''
            CREATE TABLE IF NOT EXISTS image_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comparison_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT,
                image_size TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (comparison_id) REFERENCES comparisons (id)
            )
        ''')
        
        # Create indices for performance
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_image_metadata_comparison 
            ON image_metadata(comparison_id)
        ''')
        
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_image_metadata_filename 
            ON image_metadata(filename)
        ''')
    
    # Store the metadata
    c.execute(
        'INSERT OR REPLACE INTO image_metadata (comparison_id, filename, original_filename, image_size) VALUES (?, ?, ?, ?)',
        (comparison_id, filename, original_filename, image_size)
    )
    
    conn.commit()
    conn.close()
