"""
Authentication module for Comps.
Handles user authentication, invitation codes, and session management.
"""
import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator
from datetime import datetime, timedelta
from fastapi import Request
from fastapi.security import APIKeyCookie
from jose import JWTError, jwt

# Constants
DB_PATH = os.getenv('DB_PATH', 'comparisons.db')
# Load secret key from environment or generate one.
# In a production environment, this MUST be a persistent value.
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

if "SECRET_KEY" not in os.environ:
    print("Warning: SECRET_KEY not set in environment. Using a temporary key.")

# Cookie security
cookie_sec = APIKeyCookie(name="session")

@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for a database cursor."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        yield conn.cursor()
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def hash_invitation_code(code: str) -> str:
    """Hash an invitation code for secure storage"""
    return hashlib.sha256(code.encode()).hexdigest()

def create_invitation_code(created_by_id: int) -> str:
    """Create a new invitation code"""
    code = secrets.token_urlsafe(16)
    with get_db_cursor() as cursor:
        cursor.execute(
            'INSERT INTO invitation_codes (code, created_by) VALUES (?, ?)',
            (code, created_by_id)
        )
    return code

def verify_invitation_code(code: str) -> bool:
    """Verify if an invitation code is valid and unused"""
    with get_db_cursor() as cursor:
        cursor.execute('SELECT is_used FROM invitation_codes WHERE code = ?', (code,))
        result = cursor.fetchone()
    return result is not None and not result[0]

def register_user(username: str, invitation_code: str) -> Optional[Dict[str, Any]]:
    """Register a new user with an invitation code"""
    if not verify_invitation_code(invitation_code):
        return None

    code_hash = hash_invitation_code(invitation_code)
    try:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                return None

            cursor.execute(
                'INSERT INTO users (username, invitation_code_hash, never_expire_comparisons) '
                'VALUES (?, ?, ?)',
                (username, code_hash, 1)
            )
            user_id = cursor.lastrowid

            cursor.execute(
                'UPDATE invitation_codes SET is_used = 1, used_by = ? WHERE code = ?',
                (user_id, invitation_code)
            )

            cursor.execute(
                'SELECT id, username, is_admin, never_expire_comparisons FROM users WHERE id = ?',
                (user_id,)
            )
            user = cursor.fetchone()

        if user:
            return {
                "id": user[0],
                "username": user[1],
                "is_admin": bool(user[2]),
                "never_expire_comparisons": bool(user[3]),
            }
        return None
    except sqlite3.Error as e:
        print(f"Database error during registration: {e}")
        return None

def authenticate_user(username: str, invitation_code: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user with their username and invitation code"""
    code_hash = hash_invitation_code(invitation_code)
    with get_db_cursor() as cursor:
        cursor.execute(
            'SELECT id, username, is_admin, never_expire_comparisons FROM users '
            'WHERE username = ? AND invitation_code_hash = ?',
            (username, code_hash)
        )
        user = cursor.fetchone()

    if user:
        return {
            "id": user[0],
            "username": user[1],
            "is_admin": bool(user[2]),
            "never_expire_comparisons": bool(user[3]),
        }
    return None

def create_access_token(data: dict) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get the current user if logged in, otherwise return None"""
    session = request.cookies.get("session")
    if not session:
        return None

    try:
        payload = jwt.decode(session, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None

        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT id, username, is_admin, never_expire_comparisons, is_super_admin '
                'FROM users WHERE id = ?',
                (user_id,)
            )
            user = cursor.fetchone()

        if user:
            return {
                "id": user[0],
                "username": user[1],
                "is_admin": bool(user[2]),
                "never_expire_comparisons": bool(user[3]),
                "is_super_admin": bool(user[4]),
            }
        return None
    except (JWTError, sqlite3.Error) as e:
        print(f"Error getting optional user: {e}")
        return None

def get_user_invitation_codes(user_id: int) -> list:
    """Get all invitation codes created by a user"""
    with get_db_cursor() as cursor:
        cursor.execute('''
            SELECT ic.code, ic.is_used, u.username, ic.created_at
            FROM invitation_codes ic
            LEFT JOIN users u ON ic.used_by = u.id
            WHERE ic.created_by = ?
            ORDER BY ic.created_at DESC
        ''', (user_id,))
        codes = [
            {
                "code": f"{code[:4]}...{code[-4:]}" if is_used else code,
                "is_used": bool(is_used),
                "used_by": used_by,
                "created_at": created_at,
            }
            for code, is_used, used_by, created_at in cursor.fetchall()
        ]
    return codes

def is_admin(user: dict) -> bool:
    """Check if a user is an admin"""
    return user and user.get("is_admin", False)

def is_super_admin(user: dict) -> bool:
    """Check if a user is a super admin"""
    return user and user.get("is_super_admin", False)

def get_all_users() -> list:
    """Get all users from the database"""
    with get_db_cursor() as cursor:
        cursor.execute(
            'SELECT id, username, is_admin, is_super_admin, created_at '
            'FROM users ORDER BY created_at DESC'
        )
        users = [
            {
                "id": row[0],
                "username": row[1],
                "is_admin": bool(row[2]),
                "is_super_admin": bool(row[3]),
                "created_at": row[4],
            }
            for row in cursor.fetchall()
        ]
    return users

def set_admin_status(user_id: int, admin_status: bool):
    """Set the admin status for a user"""
    with get_db_cursor() as cursor:
        cursor.execute(
            'UPDATE users SET is_admin = ? WHERE id = ? AND is_super_admin = 0',
            (1 if admin_status else 0, user_id)
        )
