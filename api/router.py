from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import uuid
import os
import shutil
from pathlib import Path
from typing import List, Optional
import json
import sqlite3
from datetime import datetime

from .models import (
    ComparisonCreate, 
    ComparisonResponse, 
    ComparisonDetail,
    ImageDetail,
    CustomNameUpdate
)
from database import (
    create_comparison, 
    get_comparison, 
    store_image_position, 
    store_image_metadata, 
    update_image_custom_name,
    update_last_accessed
)

router = APIRouter(prefix="/api/v1", tags=["api"])

# Environment variables
# Constants
MAX_ROWS = 20

UPLOADS_PATH = os.getenv('UPLOADS_PATH', 'uploads')
DB_PATH = os.getenv('DB_PATH', 'comparisons.db')

@router.get("/comparisons", response_model=List[ComparisonResponse])
async def list_comparisons():
    """
    List all available comparisons.
    
    Returns a list of all comparisons with their basic metadata including:
    - ID, name, and show name
    - Tags
    - Grid dimensions (rows and columns)
    - Expiration settings
    - Creation and last accessed timestamps
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT id, name, show_name, total_rows, total_columns, expiration_type, expiration_days, created_at, last_accessed FROM comparisons ORDER BY created_at DESC')
    comparisons = []
    
    for row in c.fetchall():
        comparison_id = row['id']
        c.execute('SELECT tag FROM tags WHERE comparison_id = ?', (comparison_id,))
        tags = [tag_row[0] for tag_row in c.fetchall()]
        
        comparison = dict(row)
        comparison['tags'] = tags
        comparisons.append(comparison)
    
    conn.close()
    return comparisons

@router.post("/comparisons", response_model=ComparisonResponse, status_code=201)
async def create_new_comparison(comparison: ComparisonCreate):
    """
    Create a new comparison.

    Creates a new comparison with the specified parameters:
    - Name and show name (optional)
    - Tags for categorization (optional)
    - Grid dimensions (rows and columns, max 20 rows)
    - Expiration settings
    """
    comparison_id = str(uuid.uuid4())
    
    # Prepare metadata
    metadata = {
        "total_columns": comparison.total_columns,
        "total_rows": comparison.total_rows,
    }
    
    # Enforce maximum rows limit
    metadata["total_rows"] = min(metadata["total_rows"], MAX_ROWS)
    
    # Create comparison directory
    comparison_dir = Path(UPLOADS_PATH) / comparison_id
    comparison_dir.mkdir(exist_ok=True, parents=True)
    
    # Store in database
    create_comparison(
        comparison_id=comparison_id,
        name=comparison.name,
        show_name=comparison.show_name,
        tags=comparison.tags,
        metadata=metadata
    )
    
    # Get the created comparison
    result = get_comparison(comparison_id)
    return result

@router.get("/comparisons/{comparison_id}", response_model=ComparisonDetail)
async def get_comparison_detail(comparison_id: str):
    """
    Get detailed information about a specific comparison.
    
    Returns comprehensive information about the comparison including:
    - Basic metadata (ID, name, show name, tags)
    - Grid dimensions (rows and columns)
    - Expiration settings
    - Creation and last accessed timestamps
    - Complete list of images with their positions and metadata
    
    This endpoint also updates the last_accessed timestamp for the comparison.
    """
    # Update last accessed timestamp
    update_last_accessed(comparison_id)
    
    # Get comparison data
    comparison_data = get_comparison(comparison_id)
    if not comparison_data:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    # Get image positions and metadata
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        SELECT ip.filename, ip.column_position, ip.row_number, 
               im.original_filename, im.image_size, im.custom_name
        FROM image_positions ip
        LEFT JOIN image_metadata im ON ip.comparison_id = im.comparison_id AND ip.filename = im.filename
        WHERE ip.comparison_id = ?
        ORDER BY ip.row_number ASC, ip.column_position ASC
    ''', (comparison_id,))
    
    images = []
    for row in c.fetchall():
        filename, column, row_num, original_filename, image_size, custom_name = row
        images.append({
            "filename": filename,
            "original_filename": original_filename,
            "custom_name": custom_name,
            "image_size": image_size,
            "row": row_num,
            "column": column
        })
    
    conn.close()
    
    # Add images to the response
    comparison_data["images"] = images
    return comparison_data

@router.post("/comparisons/{comparison_id}/images", status_code=201)
async def upload_images(
    comparison_id: str,
    files: List[UploadFile] = File(...),
    positions: str = Form(None)
):
    """
    Upload images to an existing comparison.
    
    Upload one or more image files to a comparison and specify their positions in the grid.
    
    - Files should be image files (jpg, jpeg, png, bmp, webp)
    - Positions can be specified as a JSON string mapping filenames to grid positions
    
    Example positions JSON:
    ```json
    {
        "image1.jpg": {"row": 0, "column": 0},
        "image2.jpg": {"row": 0, "column": 1}
    }
    ```
    """
    # Check if comparison exists
    comparison_data = get_comparison(comparison_id)
    if not comparison_data:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    # Parse positions if provided
    positions_data = {}
    if positions:
        try:
            positions_data = json.loads(positions)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid positions JSON format")
    
    comparison_dir = Path(UPLOADS_PATH) / comparison_id
    if not comparison_dir.exists():
        comparison_dir.mkdir(exist_ok=True, parents=True)
    
    uploaded_files = []
    
    for file_index, file in enumerate(files):
        original_filename = file.filename
        file_ext = Path(file.filename).suffix
        save_path = comparison_dir / f"{uuid.uuid4()}{file_ext}"
        
        if not file_ext.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")
        
        try:
            with save_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Determine row and column position
            if original_filename in positions_data:
                row_position = positions_data[original_filename]["row"]
                column_index = positions_data[original_filename]["column"]
            else:
                # Default sequential positioning
                column_index = file_index % comparison_data["total_columns"]
                row_position = file_index // comparison_data["total_columns"]
            
            store_image_position(comparison_id, save_path.name, row_position, column_index)
            
            # Store image metadata
            image_size = f"{file.size} bytes"
            store_image_metadata(comparison_id, save_path.name, original_filename, image_size)
            
            uploaded_files.append({
                "filename": save_path.name,
                "original_filename": original_filename,
                "row": row_position,
                "column": column_index
            })
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    return {"uploaded": uploaded_files}

@router.put("/comparisons/{comparison_id}/images/{filename}", status_code=200)
async def update_image_metadata(
    comparison_id: str,
    filename: str,
    update_data: CustomNameUpdate
):
    """
    Update image metadata.
    
    Currently supports updating:
    - Custom name for the image
    
    The custom name can be used to provide a more descriptive label for the image
    that will be displayed in the UI.
    """
    # Check if comparison exists
    comparison_data = get_comparison(comparison_id)
    if not comparison_data:
        raise HTTPException(status_code=404, detail="Comparison not found")
    
    # Check if file exists
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT filename FROM image_metadata WHERE comparison_id = ? AND filename = ?', 
              (comparison_id, filename))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Image not found")
    conn.close()
    
    # Update custom name
    update_image_custom_name(comparison_id, filename, update_data.custom_name)
    
    return {"message": "Image metadata updated successfully"}
