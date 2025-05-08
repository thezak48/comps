import sqlite3
import os
import shutil
from datetime import datetime, timedelta
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
        'INSERT INTO comparisons (id, name, show_name, total_rows, total_columns, expiration_type, expiration_days) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (comparison_id, name, show_name, metadata.get('total_rows', 1), metadata.get('total_columns', 2), metadata.get('expiration_type', 'from_last_access'), metadata.get('expiration_days', 7))
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

def update_last_accessed(comparison_id: str):
    """Update the last_accessed timestamp for a comparison"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if last_accessed column exists
        c.execute("PRAGMA table_info(comparisons)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'last_accessed' in columns:
            c.execute('UPDATE comparisons SET last_accessed = CURRENT_TIMESTAMP WHERE id = ?', (comparison_id,))
    except Exception as e:
        print(f"Error updating last_accessed: {str(e)}")
    conn.commit()
    conn.close()

def get_comparison(comparison_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('SELECT id, name, show_name, total_rows, total_columns, expiration_type, expiration_days FROM comparisons WHERE id = ?', (comparison_id,))
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
            'total_columns': comparison[4],
            'expiration_type': comparison[5],
            'expiration_days': comparison[6]
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
                custom_name TEXT,
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

def update_image_custom_name(comparison_id: str, filename: str, custom_name: str):
    """
    Update the custom name for an image
    
    Args:
        comparison_id: The UUID of the comparison
        filename: The UUID-based filename in the filesystem
        custom_name: The custom name provided by the user
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute(
        'UPDATE image_metadata SET custom_name = ? WHERE comparison_id = ? AND filename = ?',
        (custom_name, comparison_id, filename)
    )
    
    conn.commit()
    conn.close()

def get_expired_comparisons(retention_days: int):
    """
    Get a list of comparisons that haven't been accessed in more than retention_days
    
    Args:
        retention_days: Number of days to keep comparisons
        
    Returns:
        List of comparison IDs that are older than the retention period
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    expired_ids = []

    try:
        # Check if expiration columns exist
        c.execute("PRAGMA table_info(comparisons)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'last_accessed' in columns and 'expiration_type' in columns and 'expiration_days' in columns:
            # Get all comparisons with their expiration settings
            c.execute('SELECT id, expiration_type, expiration_days, created_at, last_accessed FROM comparisons')
            comparisons = c.fetchall()
            
            current_time = datetime.now()
            for comp_id, exp_type, exp_days, created_at, last_accessed in comparisons:
                # Use comparison's own expiration days if available, otherwise use default
                days = exp_days if exp_days is not None else retention_days
                
                if exp_type == 'from_creation' and created_at:
                    cutoff_date = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S') + timedelta(days=days)
                    if current_time > cutoff_date:
                        expired_ids.append(comp_id)
                elif exp_type == 'from_last_access' and last_accessed:
                    cutoff_date = datetime.strptime(last_accessed, '%Y-%m-%d %H:%M:%S') + timedelta(days=days)
                    if current_time > cutoff_date:
                        expired_ids.append(comp_id)
        else:
            # If column doesn't exist, return empty list
            expired_ids = []
    except Exception as e:
        print(f"Error getting expired comparisons: {str(e)}")
        expired_ids = []
    finally:
        conn.close()
    return expired_ids

def delete_comparison(comparison_id: str, uploads_path: str):
    """
    Delete a comparison and all associated data
    
    Args:
        comparison_id: The UUID of the comparison to delete
        uploads_path: Path to the uploads directory
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Delete all related records
    c.execute('DELETE FROM image_positions WHERE comparison_id = ?', (comparison_id,))
    c.execute('DELETE FROM image_metadata WHERE comparison_id = ?', (comparison_id,))
    c.execute('DELETE FROM tags WHERE comparison_id = ?', (comparison_id,))
    c.execute('DELETE FROM comparisons WHERE id = ?', (comparison_id,))
    
    conn.commit()
    conn.close()
    
    # Delete the comparison directory and all files
    comparison_dir = os.path.join(uploads_path, comparison_id)
    if os.path.exists(comparison_dir):
        shutil.rmtree(comparison_dir)
