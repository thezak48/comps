#!/usr/bin/env python3
"""
Script to generate OpenAPI specification from the FastAPI app.
This extracts the OpenAPI JSON and saves it to the api_docs directory.
"""

import json
import os
import sys
from pathlib import Path

# Add the parent directory to sys.path to import the main app
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from main import app
except ImportError:
    print("Error: Could not import the FastAPI app from main.py")
    sys.exit(1)

def generate_openapi_spec():
    """Generate OpenAPI specification from the FastAPI app."""
    # Create the api_docs directory if it doesn't exist
    output_dir = Path("api_docs")
    output_dir.mkdir(exist_ok=True)
    
    # Get the OpenAPI schema from the FastAPI app
    openapi_schema = app.openapi()
    
    # Save the OpenAPI schema to a JSON file
    output_path = output_dir / "openapi.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    
    print(f"OpenAPI specification generated at {output_path}")
    return str(output_path)

if __name__ == "__main__":
    generate_openapi_spec()
