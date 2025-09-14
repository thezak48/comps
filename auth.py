"""
Authentication module for Comps.
Handles user authentication, invitation codes, and session management.
"""

import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Generator, Optional

from fastapi import Request
from fastapi.security import APIKeyCookie, APIKeyHeader
from jose import JWTError, jwt

# Constants
DB_PATH = os.getenv("DB_PATH", "comparisons.db")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

if "SECRET_KEY" not in os.environ:
    print("Warning: SECRET_KEY not set in environment. Using a temporary key.")

# Cookie security
cookie_sec = APIKeyCookie(name="session")
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


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
            "INSERT INTO invitation_codes (code, created_by) VALUES (?, ?)",
            (code, created_by_id),
        )
    return code


def verify_invitation_code(code: str) -> bool:
    """Verify if an invitation code is valid and unused"""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT is_used FROM invitation_codes WHERE code = ?", (code,))
        result = cursor.fetchone()
    return result is not None and not result[0]


def register_user(username: str, invitation_code: str) -> Optional[Dict[str, Any]]:
    """Register a new user with an invitation code"""
    if not verify_invitation_code(invitation_code):
        return None

    code_hash = hash_invitation_code(invitation_code)
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return None

            cursor.execute(
                """
                INSERT INTO users (username, invitation_code_hash, never_expire_comparisons)
                VALUES (?, ?, ?)
                """,
                (username, code_hash, 1),
            )
            user_id = cursor.lastrowid

            cursor.execute(
                """
                UPDATE invitation_codes SET is_used = 1, used_by = ? WHERE code = ?
                """,
                (user_id, invitation_code),
            )

            cursor.execute(
                """
                SELECT id, username, is_admin, never_expire_comparisons FROM users WHERE id = ?
                """,
                (user_id,),
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
            """
            SELECT id, username, is_admin, never_expire_comparisons FROM users
            WHERE username = ? AND invitation_code_hash = ?
            """,
            (username, code_hash),
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


async def get_current_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes a JWT token and retrieves the user."""
    if not token:
        return None
    try:
        # Handle "Bearer <token>" format
        if token.startswith("Bearer "):
            token = token.split(" ")[1]

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None

        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, is_admin, never_expire_comparisons, is_super_admin
                FROM users WHERE id = ?
                """,
                (user_id,),
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
    except (JWTError, sqlite3.Error):
        return None


def get_user_invitation_codes(user_id: int) -> list:
    """Get all invitation codes created by a user."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT code, created_at, used_by
            FROM invitation_codes WHERE created_by = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        codes = cursor.fetchall()
        return [
            {
                "code": row[0],
                "created_at": row[1],
                "is_used": bool(row[2]),
            }
            for row in codes
        ]


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
            """
            SELECT id, username, is_admin, is_super_admin, created_at
            FROM users ORDER BY created_at DESC
            """
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
        cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (admin_status, user_id))


# --- API Key Management ---


def create_api_key(user_id: int, key_name: str) -> str:
    """Generate a new API key for a user and store its hash."""
    api_key = f"comps_{secrets.token_urlsafe(32)}"
    prefix = api_key[:12]  # e.g., "comps_AbCdEfG"
    hashed_key = hashlib.sha256(api_key.encode()).hexdigest()

    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO api_keys (user_id, key_name, key_prefix, hashed_key) VALUES (?, ?, ?, ?)",
            (user_id, key_name, prefix, hashed_key),
        )
    return api_key


def get_user_api_keys(user_id: int) -> list:
    """Get all API keys for a specific user."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, key_name, key_prefix, created_at, last_used_at
            FROM api_keys
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        keys = cursor.fetchall()
        return [
            {
                "id": row[0],
                "key_name": row[1],
                "key_prefix": row[2],
                "created_at": row[3],
                "last_used_at": row[4],
            }
            for row in keys
        ]


def delete_api_key(user_id: int, key_id: int) -> bool:
    """Delete an API key belonging to a user."""
    with get_db_cursor() as cursor:
        # Ensure the key belongs to the user before deleting
        cursor.execute("DELETE FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
        return cursor.rowcount > 0


def get_user_from_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Validate an API key and return the associated user."""
    if not api_key.startswith("comps_"):
        return None

    prefix = api_key[:12]
    hashed_key = hashlib.sha256(api_key.encode()).hexdigest()

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT u.id, u.username, u.is_admin, u.never_expire_comparisons, u.is_super_admin
            FROM users u
            JOIN api_keys ak ON u.id = ak.user_id
            WHERE ak.key_prefix = ? AND ak.hashed_key = ?
            """,
            (prefix, hashed_key),
        )
        user_row = cursor.fetchone()

        if user_row:
            # Update last used timestamp
            cursor.execute(
                "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_prefix = ?",
                (prefix,),
            )
            return {
                "id": user_row[0],
                "username": user_row[1],
                "is_admin": bool(user_row[2]),
                "never_expire_comparisons": bool(user_row[3]),
                "is_super_admin": bool(user_row[4]),
            }
    return None


async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get the current user from API Key or session cookie."""
    # 1. Try API Key from Authorization header
    auth_header = await api_key_header(request)
    if auth_header:
        # Check for "Bearer" for JWTs, otherwise assume API Key
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ")[1]
            user = await get_current_user_from_token(token)
        else:  # Treat as an API Key
            user = get_user_from_api_key(auth_header)

        if user:
            return user

    # 2. Fallback to session cookie for web UI
    session_token = request.cookies.get("session")
    if session_token:
        return await get_current_user_from_token(session_token)

    return None
