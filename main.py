"""
FastAPI application for Comps.
Handles file uploads, comparison viewing, and database operations.
"""
# Standard library imports
import logging
import os
import re
import shutil
import sqlite3
import uuid
import json
from pathlib import Path

# Third-party imports
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Local imports
from database import init_db, create_comparison, get_comparison, store_image_position, store_image_metadata

app = FastAPI(title="Comps")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration from environment
DB_PATH = os.getenv('DB_PATH', 'comparisons.db')
UPLOADS_PATH = os.getenv('UPLOADS_PATH', 'uploads')

# Ensure directories exist
Path(UPLOADS_PATH).mkdir(parents=True, exist_ok=True)
Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)

# Initialize database
init_db()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_PATH), name="uploads")
templates = Jinja2Templates(directory="templates")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

@app.get("/")
async def home(request: Request):
    """Render the home page with upload form."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload/")
async def upload_images(
    files: list[UploadFile] = File(...),
    name: str = Form(None),
    show_name: str = Form(None),
    tags: str = Form(None),
    column_order: str = Form(None)  # Parameter to receive column order
):
    """
    Handle image upload requests.
    Process multiple files and store them with metadata.
    """
    logger.info("Upload request received with %d files", len(files))
    comparison_id = str(uuid.uuid4())
    logger.info("Generated comparison ID: %s", comparison_id)
    
    if not files:
        logger.error("No files received in upload request")
        return {"error": "No files were uploaded"}
    if len(files) < 1:
        logger.error("Empty files list received")
        return {"error": "Please upload at least one image"}
    
    # Default column count is based on number of files, min 2
    total_columns = min(max(2, len(files)), 10)  # Limit to 10 columns
    total_rows = 1  # Default to one row initially
    
    # Parse column order if provided
    column_prefixes = None
    if column_order:
        try:
            column_prefixes = json.loads(column_order)
            logger.info("Received custom column order: %s", column_prefixes)
        except json.JSONDecodeError:
            logger.error("Failed to parse column order JSON: %s", column_order)
    
    # Check if files follow the old naming pattern
    pattern_files = []
    for file in files:
        match = re.match(r'^(first|second|third)(\d{4})\.', file.filename, re.IGNORECASE)
        if match:
            pattern_files.append(file)
    
    # If all files follow the pattern and no custom order is provided, use the old grouping logic
    if pattern_files and len(pattern_files) == len(files) and not column_prefixes:
        # Group files by prefix to calculate rows
        file_groups = {}
        for file in files:
            logger.info("Processing file for grouping: %s", file.filename)
            match = re.match(r'^(first|second|third)(\d{4})\.', file.filename, re.IGNORECASE)
            if match:
                prefix, number = match.groups()
                row_num = int(number)
                if row_num not in file_groups:
                    file_groups[row_num] = []
                file_groups[row_num].append((prefix.lower(), file))
        
        # Calculate total rows and images per row
        total_columns = len(set(col for group in file_groups.values() for col, _ in group))
        total_rows = len(file_groups)
    else:
        # For arbitrary filenames or custom column order, create a mapping
        file_mapping = {}
        for i, file in enumerate(files):
            file_mapping[file.filename] = file
            
        # If we have a custom column order, use it to organize files
        if column_prefixes:
            # Custom column arrangement
            total_columns = len(column_prefixes)
    
    # Store actual column count in metadata
    comparison_metadata = {"total_columns": total_columns, "total_rows": total_rows}

    comparison_dir = Path(UPLOADS_PATH) / comparison_id
    logger.info("Creating comparison directory: %s", comparison_dir)
    comparison_dir.mkdir(exist_ok=True)
    
    uploaded_files = []
    
    # Create a mapping between files and their intended column positions
    file_column_mapping = {}
    
    # Using custom column order when available
    if column_prefixes:
        # Process files in upload order but assign column positions based on column_prefixes
        for i, file in enumerate(files):
            file_ext = Path(file.filename).suffix
            save_path = comparison_dir / f"{uuid.uuid4()}{file_ext}"
            
            # Determine which column this file should be in based on upload order
            column_index = i % total_columns
            
            # Store the file's intended column position using the reordered columns
            # This is the key fix: we map the original column index to the reordered index
            file_column_mapping[file.filename] = column_index
    
    # Process and save all files
    for file_index, file in enumerate(files):
        logger.info("Processing file: %s", file.filename)
        original_filename = file.filename
        file_ext = Path(file.filename).suffix
        save_path = comparison_dir / f"{uuid.uuid4()}{file_ext}"
        
        if not file_ext.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
            logger.error("Invalid file type received: %s", file_ext)
            return {"error": f"Unsupported file type: {file_ext}"}
        
        try:
            with save_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            logger.info("Successfully saved file to: %s", save_path)
            
            # Determine column position based on the file naming pattern or custom order
            if pattern_files and not column_prefixes:
                # Pattern-based positioning logic (original)
                match = re.match(r'^(first|second|third)(\d{4})\.', original_filename, re.IGNORECASE)
                if match:
                    prefix, number = match.groups()
                    column_index = ['first', 'second', 'third'].index(prefix.lower())
                    row_position = int(number) - 1
                else:
                    # Sequential positioning for non-pattern files
                    column_index = file_index % total_columns
                    row_position = file_index // total_columns
            elif column_prefixes:
                # Use custom ordering from column_prefixes
                original_column = file_index % total_columns
                
                # Look up the new column index in column_prefixes based on original order
                # This maps the sequential column to the reordered column
                column_name = f"column{original_column+1}"
                try:
                    # Find where this column is in the reordered list
                    new_column_index = column_prefixes.index(column_name)
                    column_index = new_column_index
                except ValueError:
                    # Fallback if column name not found
                    column_index = original_column
                
                row_position = file_index // total_columns
            else:
                # Default sequential positioning
                column_index = file_index % total_columns
                row_position = file_index // total_columns
            
            store_image_position(comparison_id, save_path.name, row_position, column_index)
            
            # Store image metadata
            image_size = f"{file.size} bytes"
            store_image_metadata(comparison_id, save_path.name, original_filename, image_size)
        except Exception as e:
            logger.error("Error saving file: %s", str(e))
            return {"error": f"Failed to save file: {str(e)}"}
        
        uploaded_files.append(f"{comparison_id}/{save_path.name}")
    
    # Store metadata in database
    tag_list = tags.split(',') if tags else []
    create_comparison(
        comparison_id=comparison_id,
        name=name,
        show_name=show_name,
        tags=tag_list,
        metadata=comparison_metadata
    )
    logger.info("Upload completed successfully with %d files", len(uploaded_files))
    return {"comparison_id": comparison_id, "files": uploaded_files, "metadata": comparison_metadata}

@app.get("/compare/{comparison_id}")
async def compare_images(request: Request, comparison_id: str):
    comparison_dir = Path(UPLOADS_PATH) / comparison_id
    if not comparison_dir.exists():
        return {"error": "Comparison not found"}

    # Get image positions from database
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT filename, column_position, row_number 
        FROM image_positions 
        WHERE comparison_id = ?
        ORDER BY row_number ASC, column_position ASC
    ''', (comparison_id,))
    
    ordered_images = []
    image_names = []
    image_sizes = []
    for filename, column, row in c.fetchall():
        # Get original filename and size from the database
        c.execute('''
            SELECT original_filename, image_size 
            FROM image_metadata 
            WHERE comparison_id = ? AND filename = ?
        ''', (comparison_id, filename))
        metadata = c.fetchone()
        if metadata:
            original_name, size = metadata
            image_names.append(original_name)
            image_sizes.append(size)
        else:
            image_names.append(filename)
            image_sizes.append('')
        ordered_images.append(f"{comparison_id}/{filename}")
    
    conn.close()

    # Get comparison metadata
    comparison_data = get_comparison(comparison_id)
    
    # Set default values for total_columns and total_rows if not in metadata
    total_columns = comparison_data.get('total_columns', 2) if comparison_data else 2
    total_rows = comparison_data.get('total_rows', 1) if comparison_data else 1
    
    return templates.TemplateResponse(
        "compare.html",
        {"request": request, "images": ordered_images, 
         "metadata": comparison_data,
         "image_names": image_names,
         "image_sizes": image_sizes,
         "total_columns": total_columns,
         "total_rows": total_rows}
    )
