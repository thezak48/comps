import pytest
import os
import sqlite3
from jose import jwt

from auth import (
    hash_invitation_code,
    create_invitation_code,
    verify_invitation_code,
    register_user,
    authenticate_user,
    create_access_token,
    SECRET_KEY,
    ALGORITHM
)

def test_hash_invitation_code():
    """Test that invitation codes are hashed consistently"""
    code = "test-invitation-code"
    hash1 = hash_invitation_code(code)
    hash2 = hash_invitation_code(code)
    
    assert hash1 == hash2
    assert hash1 != code  # Make sure it's actually hashed

def test_create_access_token():
    """Test creating and decoding JWT tokens"""
    # Create a token with test data
    data = {"sub": "123", "name": "Test User"}
    token = create_access_token(data)
    
    # Decode the token
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    
    # Check the payload contains our data
    assert payload["sub"] == data["sub"]
    assert payload["name"] == data["name"]
    assert "exp" in payload  # Should have an expiration
