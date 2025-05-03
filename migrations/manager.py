import os
import sqlite3
import importlib
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class MigrationManager:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.versions_path = Path(__file__).parent / 'versions'
        
    def get_current_version(self):
        """Get the current database version"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT version FROM migrations ORDER BY id DESC LIMIT 1')
                result = cursor.fetchone()
                return result[0] if result else None
            except sqlite3.OperationalError:
                return None

    def get_available_migrations(self):
        """Get list of available migration files"""
        migrations = []
        for file in sorted(self.versions_path.glob('[0-9]*.py')):
            if file.stem != '__init__':
                version = file.stem.split('_')[0]
                migrations.append((version, file))
        return migrations

    def apply_migration(self, version, migration_path):
        """Apply a single migration"""
        module_name = f"migrations.versions.{migration_path.stem}"
        migration = importlib.import_module(module_name)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                # Create migrations table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version TEXT NOT NULL,
                        name TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        success BOOLEAN DEFAULT 0
                    )
                ''')
                
                # Apply migration
                migration.upgrade(cursor)
                
                # Record successful migration
                cursor.execute(
                    'INSERT INTO migrations (version, name, success) VALUES (?, ?, ?)',
                    (version, migration_path.stem, True)
                )
                conn.commit()
                logger.info(f"Successfully applied migration: {version}")
                return True
            except Exception as e:
                logger.error(f"Failed to apply migration {version}: {str(e)}")
                conn.rollback()
                return False

    def migrate(self, db_path=None):
        """Run all pending migrations"""
        self.db_path = db_path or os.getenv('DB_PATH', 'comparisons.db')
        current = self.get_current_version()
        available = self.get_available_migrations()
        
        for version, migration_path in available:
            if not current or version > current:
                logger.info(f"Applying migration: {version}")
                if not self.apply_migration(version, migration_path):
                    break
