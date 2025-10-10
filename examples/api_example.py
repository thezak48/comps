#!/usr/bin/env python3
"""
Example script demonstrating the use of the Comps API for creating comparisons and uploading images
"""
import argparse
import json
import re
import sys
from pathlib import Path

import requests

# Supported image file extensions
SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"]


def natural_sort_key(path):
    """
    A key for natural sorting of filenames.
    It splits the filename into text and number parts.
    e.g. "image10.png" -> ["image", 10, ".png"]
    """
    return [
        int(text) if text.isdigit() else text.lower() for text in re.split("([0-9]+)", path.name)
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Comps API Example. Creates a comparison from images in specified directories.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for Comps")
    parser.add_argument("--name", default="", help="Comparison name")
    parser.add_argument(
        "--column",
        action="append",
        required=True,
        dest="columns",
        help=(
            "Directory of images for a column. Specify this for each column.\n"
            "Example: --column ./col1 --column ./col2"
        ),
    )
    parser.add_argument(
        "--api-key", required=True, help="Your personal API key for authentication."
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        default=[],
        help="A space-separated list of tags for the comparison.",
    )

    args = parser.parse_args()

    # --- Process Image Directories ---
    column_images = []
    for col_dir in args.columns:
        path = Path(col_dir)
        if not path.is_dir():
            print(f"Error: Column directory not found at '{col_dir}'")
            sys.exit(1)

        images = sorted(
            [p for p in path.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS],
            key=natural_sort_key,
        )
        if not images:
            print(f"Warning: No supported images found in directory '{col_dir}'")

        column_images.append(images)

    if not any(column_images):
        print("Error: No images found in any of the specified column directories.")
        sys.exit(1)

    num_columns = len(column_images)
    num_rows = min(len(images) for images in column_images if images) if any(column_images) else 0

    if num_rows == 0:
        print("Error: Could not create comparison as at least one column has no images.")
        sys.exit(1)

    base_url = f"{args.url}/api/v1"
    headers = {"Authorization": args.api_key}

    # 1. Create a new comparison
    print(f"Creating new comparison: {args.name} ({num_rows} rows x {num_columns} columns)")
    comparison_data = {
        "name": args.name,
        "show_name": args.name,
        "tags": args.tags,
        "total_rows": num_rows,
        "total_columns": num_columns,
    }

    response = requests.post(
        f"{base_url}/comparisons", json=comparison_data, headers=headers, timeout=10
    )
    if response.status_code != 201:
        print(f"Error creating comparison: {response.text}")
        sys.exit(1)

    comparison = response.json()
    comparison_id = comparison["id"]
    print(f"Comparison created with ID: {comparison_id}")

    # 2. Upload images for each cell
    print("Uploading images...")
    for row_idx in range(num_rows):
        for col_idx in range(num_columns):
            path = column_images[col_idx][row_idx]

            with open(path, "rb") as f:
                file_data = {"file": (path.name, f, f"image/{path.suffix[1:]}")}
                form_data = {
                    "row": row_idx,
                    "column": col_idx,
                    "original_filename": path.name,
                }

                upload_url = f"{base_url}/comparison/{comparison_id}/image"
                print(f"  Uploading {path.name} to row {row_idx}, column {col_idx}...")
                response = requests.post(
                    upload_url,
                    files=file_data,
                    data=form_data,
                    headers=headers,
                    timeout=30,
                )

                if response.status_code != 200:
                    print(f"    Error uploading image {path.name}: {response.text}")
                else:
                    print(f"    Successfully uploaded {path.name}")

    # 3. Get comparison details
    print("\nRetrieving comparison details")
    response = requests.get(f"{base_url}/comparisons/{comparison_id}", headers=headers, timeout=10)
    if response.status_code != 200:
        print(f"Error getting comparison details: {response.text}")
        sys.exit(1)

    details = response.json()
    print(f"\nComparison URL: {args.url}/compare/{comparison_id}")
    print(f"API Details URL: {base_url}/comparisons/{comparison_id}")

    print("\nComparison details:")
    print(json.dumps(details, indent=2))

    print(f"Comparison URL: {args.url}/compare/{comparison_id}")


if __name__ == "__main__":
    main()
