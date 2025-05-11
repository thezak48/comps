import pytest
import sqlite3
import os
import uuid
from datetime import datetime, timedelta

from database import (
    create_comparison,
    get_comparison,
    store_image_position,
    store_image_metadata,
    update_image_custom_name,
    update_last_accessed,
    get_expired_comparisons,
    delete_comparison
)

def test_create_and_get_comparison(test_db):
    """Test creating and retrieving a comparison"""
    comparison_id = str(uuid.uuid4())
    name = "Test Comparison"
    show_name = "Test"
    tags = ["test", "database"]
    metadata = {
        "total_rows": 2,
        "total_columns": 3,
        "expiration_type": "from_creation",
        "expiration_days": 14
    }
    
    # Set the DB_PATH for testing
    os.environ["DB_PATH"] = ":memory:"
    
    # Create the comparison
    create_comparison(comparison_id, name, show_name, tags, metadata)
    
    # Retrieve the comparison
    comparison = get_comparison(comparison_id)
    
    # Check the retrieved data
    assert comparison is not None
    assert comparison["id"] == comparison_id
    assert comparison["name"] == name
    assert comparison["show_name"] == show_name
    assert set(comparison["tags"]) == set(tags)
    assert comparison["total_rows"] == metadata["total_rows"]
    assert comparison["total_columns"] == metadata["total_columns"]
    assert comparison["expiration_type"] == metadata["expiration_type"]
    assert comparison["expiration_days"] == metadata["expiration_days"]

def test_store_image_position(test_db):
    """Test storing image positions"""
    comparison_id = str(uuid.uuid4())
    filename = "test.jpg"
    row_number = 1
    column_position = 2
    
    # Create a comparison first
    create_comparison(comparison_id, "Test", "Test", [], {"total_rows": 2, "total_columns": 3})
    
    # Store the image position
    store_image_position(comparison_id, filename, row_number, column_position)
    
    # Verify the position was stored
    cursor = test_db.cursor()
    cursor.execute(
        "SELECT row_number, column_position FROM image_positions WHERE comparison_id = ? AND filename = ?",
        (comparison_id, filename)
    )
    result = cursor.fetchone()
    
    assert result is not None
    assert result["row_number"] == row_number
    assert result["column_position"] == column_position
