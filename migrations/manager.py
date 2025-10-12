import os
import importlib
import logging
from pathlib import Path
from datetime import datetime

from db import autoincrement_pk_sql, bool_default, connect, execute, query_one
logger = logging.getLogger(__name__)

class MigrationManager:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.versions_path = Path(__file__).parent / 'versions'
        
    def get_current_version(self):
        """Get the current database version"""
        try:
            row = query_one('SELECT version FROM migrations ORDER BY id DESC LIMIT 1')
            return row[0] if row else None
        except Exception:
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
        try:
            # Create migrations table if it doesn't exist (backend-specific PK)
            execute(
                f'''
                    CREATE TABLE IF NOT EXISTS migrations (
                        id {autoincrement_pk_sql()},
                        version TEXT NOT NULL,
                        name TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        success BOOLEAN {bool_default(False)}
                    )
                '''
            )

            # For Postgres, ensure the success column has a valid boolean default
            try:
                with connect() as (conn, cursor):
                    cursor.execute("ALTER TABLE migrations ALTER COLUMN success SET DEFAULT FALSE")
                    conn.commit()
            except Exception:
                # Ignore if not Postgres or already correct
                pass

            # Apply migration using a disposable connection/cursor
            with connect() as (conn, cursor):
                # Wrap cursor to translate placeholders on Postgres
                class AdapterCursor:
                    def __init__(self, real):
                        self._c = real

                    def execute(self, sql, params=None):
                        from db import _convert_placeholders

                        sql_conv = _convert_placeholders(sql)
                        if params is None:
                            return self._c.execute(sql_conv)
                        return self._c.execute(sql_conv, params)

                    def executemany(self, sql, seq_of_params):
                        from db import _convert_placeholders

                        sql_conv = _convert_placeholders(sql)
                        return self._c.executemany(sql_conv, seq_of_params)

                    def fetchone(self):
                        return self._c.fetchone()

                    def fetchall(self):
                        return self._c.fetchall()

                    @property
                    def rowcount(self):
                        return self._c.rowcount

                    def __getattr__(self, item):
                        return getattr(self._c, item)

                ac = AdapterCursor(cursor)
                migration.upgrade(ac)
                ac.execute(
                    'INSERT INTO migrations (version, name, success) VALUES (?, ?, ?)',
                    (version, migration_path.stem, True)
                )
                conn.commit()
            logger.info(f"Successfully applied migration: {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {str(e)}")
            return False

    def migrate(self, db_path=None):
        """Run all pending migrations"""
        self.db_path = db_path or os.getenv('DB_PATH', 'comparisons.db')
        # Ensure adapter picks up the intended SQLite path
        if db_path:
            os.environ['DB_PATH'] = str(db_path)
        current = self.get_current_version()
        available = self.get_available_migrations()
        
        for version, migration_path in available:
            if not current or version > current:
                logger.info(f"Applying migration: {version}")
                if not self.apply_migration(version, migration_path):
                    break
