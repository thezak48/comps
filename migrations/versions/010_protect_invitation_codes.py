"""Store invitation codes without recoverable cleartext once redeemed

Revision ID: 010
Revises: 009
Create Date: 2026-08-16 12:00:00

"""

# revision identifiers, used by the migration system
revision = '010'
down_revision = '009_add_comparison_edit_token'

import base64
import hashlib
import secrets

from db import backend_name

def _scrypt_hash(code):
    """Match the versioned format produced by auth._scrypt_hash."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        code.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32, maxmem=128 * 2**14 * 8 * 2
    )
    return "scrypt$16384$8$1${}${}".format(
        base64.b64encode(salt).decode(), base64.b64encode(derived).decode()
    )

def upgrade(cursor):
    """Allow cleartext to be cleared, upgrade stored hashes, then clear redeemed codes."""
    # The code column must accept NULL so a redeemed code can be discarded.
    if backend_name() == "postgres":
        cursor.execute("ALTER TABLE invitation_codes ALTER COLUMN code DROP NOT NULL")
    else:
        # SQLite cannot drop a NOT NULL constraint in place, so recreate the table.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invitation_codes_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                created_by INTEGER,
                is_used BOOLEAN DEFAULT 0,
                used_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users (id),
                FOREIGN KEY (used_by) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            INSERT INTO invitation_codes_new (id, code, created_by, is_used, used_by, created_at)
            SELECT id, code, created_by, is_used, used_by, created_at FROM invitation_codes
        ''')
        cursor.execute('DROP TABLE invitation_codes')
        cursor.execute('ALTER TABLE invitation_codes_new RENAME TO invitation_codes')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_invitation_codes_code ON invitation_codes(code)'
        )

    # Upgrade credentials to salted hashes while the cleartext is still recoverable.
    cursor.execute('''
        SELECT u.id, ic.code
        FROM users u
        JOIN invitation_codes ic ON ic.used_by = u.id
        WHERE ic.code IS NOT NULL
    ''')
    for user_id, code in cursor.fetchall():
        cursor.execute(
            'UPDATE users SET invitation_code_hash = ? WHERE id = ?',
            (_scrypt_hash(code), user_id)
        )

    # Discard the cleartext of codes that have already been redeemed.
    cursor.execute('UPDATE invitation_codes SET code = NULL WHERE is_used = ?', (True,))

def downgrade(_cursor):
    """No-op downgrade. Discarded cleartext cannot be recovered."""
