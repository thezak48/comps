import os
import sys
import pytest
import tempfile
import sqlite3
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from database import init_db

@pytest.fixture
def client():
    """Create a test client for the app"""
    # Use a temporary directory for uploads
    with tempfile.TemporaryDirectory() as temp_uploads:
        # Use an in-memory database for testing
        db_path = ":memory:"
        
        # Set environment variables for testing
        os.environ["UPLOADS_PATH"] = temp_uploads
        os.environ["DB_PATH"] = db_path
        
        # Initialize the database
        init_db()
        
        # Create a test client
        with TestClient(app) as test_client:
            yield test_client

@pytest.fixture
def test_db():
    """Create an in-memory test database"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    # Initialize the database schema
    init_db()
    
    yield conn
    
    # Close the connection
    conn.close()
