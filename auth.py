"""
Authentication module for Comps.
Handles user authentication, invitation codes, and session management.
"""
import hashlib
import os
import secrets
import sqlite3
import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends, Cookie
from fastapi.security import APIKeyCookie
from jose import JWTError, jwt
from datetime import datetime, timedelta

# Constants
DB_PATH = os.getenv('DB_PATH', 'comparisons.db')
SECRET_KEY = secrets.token_hex(32)  # Generate a random secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

# Cookie security
cookie_sec = APIKeyCookie(name="session")

def hash_invitation_code(code: str) -> str:
    """Hash an invitation code for secure storage"""
    return hashlib.sha256(code.encode()).hexdigest()

def create_invitation_code(created_by_id: int) -> str:
    """Create a new invitation code"""
    # Generate a random code
    code = secrets.token_urlsafe(16)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Store the code
    c.execute(
        'INSERT INTO invitation_codes (code, created_by) VALUES (?, ?)',
        (code, created_by_id)
    )
    
    conn.commit()
    conn.close()
    
    return code

def verify_invitation_code(code: str) -> bool:
    """Verify if an invitation code is valid and unused"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('SELECT is_used FROM invitation_codes WHERE code = ?', (code,))
    result = c.fetchone()
    
    conn.close()
    
    # Code is valid if it exists and is not used
    return result is not None and not result[0]

def register_user(username: str, invitation_code: str) -> Optional[Dict[str, Any]]:
    """Register a new user with an invitation code"""
    if not verify_invitation_code(invitation_code):
        return None
    
    # Hash the invitation code for storage
    code_hash = hash_invitation_code(invitation_code)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # Check if username already exists
        c.execute('SELECT id FROM users WHERE username = ?', (username,))
        if c.fetchone():
            conn.close()
            return None
        
        # Create the user
        c.execute(
            'INSERT INTO users (username, invitation_code_hash, never_expire_comparisons) VALUES (?, ?, ?)',
            (username, code_hash, 1)  # All invited users get permanent comparisons
        )
        user_id = c.lastrowid
        
        # Mark the invitation code as used
        c.execute(
            'UPDATE invitation_codes SET is_used = 1, used_by = ? WHERE code = ?',
            (user_id, invitation_code)
        )
        
        # Get the user data
        c.execute('SELECT id, username, is_admin, never_expire_comparisons FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        
        conn.commit()
        
        if user:
            return {
                "id": user[0],
                "username": user[1],
                "is_admin": bool(user[2]),
                "never_expire_comparisons": bool(user[3])
            }
        return None
    except Exception as e:
        print(f"Error registering user: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def authenticate_user(username: str, invitation_code: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user with their username and invitation code"""
    # Hash the invitation code for comparison
    code_hash = hash_invitation_code(invitation_code)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute(
        'SELECT id, username, is_admin, never_expire_comparisons FROM users WHERE username = ? AND invitation_code_hash = ?',
        (username, code_hash)
    )
    user = c.fetchone()
    
    conn.close()
    
    if user:
        return {
            "id": user[0],
            "username": user[1],
            "is_admin": bool(user[2]),
            "never_expire_comparisons": bool(user[3])
        }
    return None

def create_access_token(data: dict) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(session: str = Depends(cookie_sec)) -> Optional[Dict[str, Any]]:
    """Get the current user from the session cookie"""
    try:
        payload = jwt.decode(session, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute(
            'SELECT id, username, is_admin, never_expire_comparisons FROM users WHERE id = ?',
            (user_id,)
        )
        user = c.fetchone()
        
        conn.close()
        
        if user:
            return {
                "id": user[0],
                "username": user[1],
                "is_admin": bool(user[2]),
                "never_expire_comparisons": bool(user[3])
            }
        return None
    except JWTError:
        return None
    except Exception as e:
        print(f"Error getting current user: {e}")
        return None

def get_user_invitation_codes(user_id: int) -> list:
    """Get all invitation codes created by a user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        SELECT ic.code, ic.is_used, u.username, ic.created_at
        FROM invitation_codes ic
        LEFT JOIN users u ON ic.used_by = u.id
        WHERE ic.created_by = ?
        ORDER BY ic.created_at DESC
    ''', (user_id,))
    
    codes = []
    for code, is_used, used_by, created_at in c.fetchall():
        codes.append({
            "code": code,
            "is_used": bool(is_used),
            "used_by": used_by,
            "created_at": created_at
        })
    
    conn.close()
    return codes

def is_admin(user: dict) -> bool:
    """Check if a user is an admin"""
    return user and user.get("is_admin", False)

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
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute(
            'SELECT id, username, is_admin, never_expire_comparisons FROM users WHERE id = ?',
            (user_id,)
        )
        user = c.fetchone()
        
        conn.close()
        
        if user:
            return {
                "id": user[0],
                "username": user[1],
                "is_admin": bool(user[2]),
                "never_expire_comparisons": bool(user[3])
            }
        return None
    except JWTError:
        return None
    except Exception as e:
        print(f"Error getting optional user: {e}")
        return None
