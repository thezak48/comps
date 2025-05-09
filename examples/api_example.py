#!/usr/bin/env python3
"""
Example script demonstrating the use of the Comps API for creating comparisons and uploading images
"""
import requests
import json
import os
import sys
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Comps API Example')
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL for Comps')
    parser.add_argument('--name', default='API Test', help='Comparison name')
    parser.add_argument('--images', nargs='+', required=True, help='Images to upload')
    
    args = parser.parse_args()
    
    base_url = f"{args.url}/api/v1"
    
    # 1. Create a new comparison
    print(f"Creating new comparison: {args.name}")
    comparison_data = {
        "name": args.name,
        "show_name": args.name,
        "tags": ["api", "example"],
        "total_rows": 1,
        "total_columns": len(args.images)
    }
    
    response = requests.post(f"{base_url}/comparisons", json=comparison_data)
    if response.status_code != 201:
        print(f"Error creating comparison: {response.text}")
        sys.exit(1)
    
    comparison = response.json()
    comparison_id = comparison["id"]
    print(f"Comparison created with ID: {comparison_id}")
    
    # 2. Upload images
    print(f"Uploading {len(args.images)} images")
    files = []
    positions = {}
    
    for i, image_path in enumerate(args.images):
        path = Path(image_path)
        if not path.exists():
            print(f"Error: Image {image_path} not found")
            continue
            
        filename = path.name
        files.append(("files", (filename, open(path, "rb"), f"image/{path.suffix[1:]}")))
        positions[filename] = {"row": 0, "column": i}
    
    data = {"positions": json.dumps(positions)}
    response = requests.post(f"{base_url}/comparisons/{comparison_id}/images", files=files, data=data)
    
    if response.status_code != 201:
        print(f"Error uploading images: {response.text}")
        sys.exit(1)
    
    upload_result = response.json()
    print(f"Successfully uploaded {len(upload_result['uploaded'])} images")
    
    # 3. Get comparison details
    print("Retrieving comparison details")
    response = requests.get(f"{base_url}/comparisons/{comparison_id}")
    if response.status_code != 200:
        print(f"Error getting comparison details: {response.text}")
        sys.exit(1)
    
    details = response.json()
    print(f"Comparison URL: {args.url}/compare/{comparison_id}")
    print(f"API Details URL: {base_url}/comparisons/{comparison_id}")
    
    print("\nComparison details:")
    print(json.dumps(details, indent=2))

if __name__ == "__main__":
    main()
