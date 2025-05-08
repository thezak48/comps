"""
FastAPI application for Comps.
Handles file uploads, comparison viewing, and database operations.
"""
# Standard library imports
import asyncio
import logging
import os
import re
import shutil
import sqlite3
import uuid
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

# Third-party imports
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Local imports
from database import init_db, create_comparison, get_comparison, store_image_position, store_image_metadata, update_image_custom_name, update_last_accessed, get_expired_comparisons, delete_comparison

app = FastAPI(title="Comps")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration from environment
DB_PATH = os.getenv('DB_PATH', 'comparisons.db')
UPLOADS_PATH = os.getenv('UPLOADS_PATH', 'uploads')
RETENTION_DAYS = int(os.getenv('RETENTION_DAYS', '7'))

# Ensure directories exist
Path(UPLOADS_PATH).mkdir(parents=True, exist_ok=True)
Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)

# Initialize database
init_db()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_PATH), name="uploads")
templates = Jinja2Templates(directory="templates")

# Background task for cleanup
async def cleanup_old_comparisons():
    """
    Periodically check for and delete comparisons that haven't been accessed 
    in more than RETENTION_DAYS days
    """
    while True:
        try:
            # Check if last_accessed column exists
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("PRAGMA table_info(comparisons)")
            columns = [col[1] for col in c.fetchall()]
            conn.close()

            if 'last_accessed' in columns:
                logger.info(f"Starting cleanup of comparisons older than {RETENTION_DAYS} days")
                try:
                    expired_ids = get_expired_comparisons(RETENTION_DAYS)
                    
                    if expired_ids:
                        logger.info(f"Found {len(expired_ids)} expired comparisons to delete")
                        for comparison_id in expired_ids:
                            try:
                                logger.info(f"Deleting comparison {comparison_id}")
                                delete_comparison(comparison_id, UPLOADS_PATH)
                            except Exception as e:
                                logger.error(f"Error deleting comparison {comparison_id}: {str(e)}")
                    else:
                        logger.info("No expired comparisons found")
                except sqlite3.OperationalError as e:
                    if "no such column" in str(e):
                        logger.warning(f"Skipping cleanup: {str(e)}. Migrations may not be complete.")
                    else:
                        logger.error(f"Error in cleanup task: {str(e)}")
            else:
                logger.info("Skipping cleanup: last_accessed column not found in database")
                
            # Run once a day
            await asyncio.sleep(86400)  # 24 hours in seconds
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")
            # If there's an error, wait a bit before trying again
            await asyncio.sleep(3600)  # 1 hour in seconds

@app.on_event("startup")
async def start_cleanup_task():
    """Start the background cleanup task when the application starts"""
    asyncio.create_task(cleanup_old_comparisons())
    
    # Check if database migrations are complete
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if the migrations table exists and has entries
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'")
        if not c.fetchone():
            logger.warning("Migrations table does not exist. Database may not be properly initialized.")
        else:
            # Check if last_accessed column exists in comparisons table
            c.execute("PRAGMA table_info(comparisons)")
            columns = [col[1] for col in c.fetchall()]
            if 'last_accessed' not in columns:
                logger.warning("Database schema is missing expected columns. Migrations may not be complete.")
                logger.warning("The application may not function correctly until migrations are completed.")
        
        conn.close()
    except Exception as e:
        logger.error(f"Error checking database state: {str(e)}")

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
    custom_names: str = Form(None),  # Parameter to receive custom image names
    column_order: str = Form(None),  # Parameter to receive column order
    row_count: int = Form(1),  # Parameter to receive row count
    file_positions: str = Form(None)  # Parameter to receive file positions
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
    
    # Parse custom names if provided
    custom_names_data = {}
    if custom_names:
        try:
            custom_names_data = json.loads(custom_names)
            logger.info("Received custom names for %d files", len(custom_names_data))
        except json.JSONDecodeError:
            logger.error("Failed to parse custom names JSON: %s", custom_names)
    
    # Parse file positions if provided
    file_position_data = None
    if file_positions:
        try:
            file_position_data = json.loads(file_positions)
            logger.info("Received file position data for %d files", len(file_position_data))
        except json.JSONDecodeError:
            logger.error("Failed to parse file positions JSON: %s", file_positions)
    
    # Default column count is based on number of files, min 2
    total_columns = min(max(2, len(files)), 10)  # Limit to 10 columns
    total_rows = max(1, row_count)  # Use provided row count or default to 1
    
    # Parse column order if provided
    column_prefixes = None
    if column_order:
        try:
            column_prefixes = json.loads(column_order)
            logger.info("Received custom column order: %s", column_prefixes)
            total_columns = len(column_prefixes)
        except json.JSONDecodeError:
            logger.error("Failed to parse column order JSON: %s", column_order)
    
    # Check if files follow the old naming pattern
    pattern_files = []
    for file in files:
        match = re.match(r'^(first|second|third)(\d{4})\.', file.filename, re.IGNORECASE)
        if match:
            pattern_files.append(file)
    
    # If all files follow the pattern and no custom positions, use the old grouping logic
    if pattern_files and len(pattern_files) == len(files) and not file_position_data:
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
    
    # Store actual column count and row count in metadata
    comparison_metadata = {"total_columns": total_columns, "total_rows": total_rows}

    comparison_dir = Path(UPLOADS_PATH) / comparison_id
    logger.info("Creating comparison directory: %s", comparison_dir)
    comparison_dir.mkdir(exist_ok=True)
    
    uploaded_files = []
    
    # Create a lookup for file positions
    file_positions_lookup = {}
    if file_position_data:
        for pos in file_position_data:
            file_positions_lookup[pos['filename']] = (pos['row'], pos['column'])
    
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
            
            # Determine row and column position
            if original_filename in file_positions_lookup:
                # Use provided position from file_positions
                row_position, column_index = file_positions_lookup[original_filename]
            elif pattern_files and not file_position_data:
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
                row_position = file_index // total_columns
                
                # Look up the new column index in column_prefixes based on original order
                column_name = f"column{original_column+1}"
                try:
                    # Find where this column is in the reordered list
                    new_column_index = column_prefixes.index(column_name)
                    column_index = new_column_index
                except ValueError:
                    # Fallback if column name not found
                    column_index = original_column
            else:
                # Default sequential positioning
                column_index = file_index % total_columns
                row_position = file_index // total_columns
            
            store_image_position(comparison_id, save_path.name, row_position, column_index)
            
            # Store image metadata
            image_size = f"{file.size} bytes"
            store_image_metadata(comparison_id, save_path.name, original_filename, image_size)
            
            # Check if this file has a custom name
            if original_filename in custom_names_data:
                custom_name = custom_names_data[original_filename]
                update_image_custom_name(comparison_id, save_path.name, custom_name)
                logger.info("Updated custom name for %s to %s", original_filename, custom_name)
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

    # Update last accessed timestamp
    update_last_accessed(comparison_id)

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
    custom_names = []
    for filename, column, row in c.fetchall():
        # Get original filename and size from the database
        c.execute('''
            SELECT original_filename, image_size, custom_name 
            FROM image_metadata 
            WHERE comparison_id = ? AND filename = ?
        ''', (comparison_id, filename))
        metadata = c.fetchone()
        if metadata:
            original_name, size, custom_name = metadata
            # Use custom name if available, otherwise use original filename
            display_name = custom_name if custom_name else original_name
            image_names.append(original_name)
            image_sizes.append(size)
            custom_names.append(custom_name)
        else:
            image_names.append(filename)
            image_sizes.append('')
            custom_names.append(None)
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
         "custom_names": custom_names,
         "total_columns": total_columns,
         "total_rows": total_rows}
    )

@app.post("/admin/cleanup")
async def manual_cleanup(retention_days: int = None):
    """
    Admin endpoint to manually trigger cleanup of old comparisons
    """
    days = retention_days if retention_days is not None else RETENTION_DAYS
    expired_ids = get_expired_comparisons(days)
    
    for comparison_id in expired_ids:
        try:
            delete_comparison(comparison_id, UPLOADS_PATH)
        except Exception as e:
            logger.error(f"Error deleting comparison {comparison_id}: {str(e)}")
    
    return {"message": f"Cleanup completed. Deleted {len(expired_ids)} comparisons older than {days} days."}
