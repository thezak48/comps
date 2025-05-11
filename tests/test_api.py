import pytest
from fastapi.testclient import TestClient
import json
import os

def test_health_check(client):
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_list_comparisons(client):
    """Test listing comparisons (should be empty initially)"""
    response = client.get("/api/v1/comparisons")
    assert response.status_code == 200
    assert response.json() == []

def test_create_comparison(client):
    """Test creating a new comparison"""
    comparison_data = {
        "name": "Test Comparison",
        "show_name": "Test",
        "tags": ["test", "api"],
        "total_rows": 1,
        "total_columns": 2
    }
    
    response = client.post("/api/v1/comparisons", json=comparison_data)
    assert response.status_code == 201
    
    # Check the response contains expected fields
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Comparison"
    assert data["show_name"] == "Test"
    assert data["tags"] == ["test", "api"]
    assert data["total_rows"] == 1
    assert data["total_columns"] == 2
