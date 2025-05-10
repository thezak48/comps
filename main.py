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
from typing import List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

# Third-party imports
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

# Local imports
from database import init_db, create_comparison, get_comparison, store_image_position, store_image_metadata, update_image_custom_name, update_last_accessed, get_expired_comparisons, delete_comparison
from api.router import router as api_router

# Create FastAPI app with custom OpenAPI settings
app = FastAPI(
    title="Comps API",
    description="API for managing image comparisons",
    version="1.0.0",
    docs_url=None,  # Disable default docs
    redoc_url=None  # Disable default redoc
)

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

# Include API router
app.include_router(api_router)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_PATH), name="uploads")
templates = Jinja2Templates(directory="templates")

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Comps API",
        version="1.0.0",
        description="API for creating and managing image comparisons",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Custom Swagger UI route with dark mode
@app.get("/api/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return templates.TemplateResponse("swagger_ui.html", {"request": Request(scope={"type": "http"})})

# Serve OpenAPI schema
@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return JSONResponse(app.openapi())

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

@app.post("/upload/")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    name: str = Form(...),
    show_name: Optional[str] = Form(None),
    expiration_type: str = Form("from_last_access"),
    expiration_days: int = Form(7),
    tags: Optional[str] = Form(None),
    file_positions: Optional[str] = Form(None),
    custom_names: Optional[str] = Form(None)
):
    """
    Handle file uploads for comparison.
    
    Accepts multiple files and metadata, creates a comparison record,
    and stores the files in a unique directory.
    """
    logger.info(f"Received upload request with {len(files)} files")
    
    # Generate a unique ID for this comparison
    comparison_id = str(uuid.uuid4())
    
    # Create directory for this comparison
    comparison_dir = Path(UPLOADS_PATH) / comparison_id
    comparison_dir.mkdir(parents=True, exist_ok=True)
    
    # Process tags
    tag_list = []
    if tags and tags.strip():
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
    
    # Process file positions if provided
    positions_data = {}
    if file_positions:
        try:
            positions_data = json.loads(file_positions)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid file positions format"}
            )
    
    # Process custom names if provided
    custom_names_data = {}
    if custom_names:
        if not name or name.strip() == '':
            return JSONResponse(
                status_code=400,
                content={"error": "Please provide a comparison name"}
            )
        if len(files) < 2:
            return JSONResponse(
                status_code=400,
                content={"error": "Please upload at least 2 files for comparison"}
            )
        try:
            custom_names_data = json.loads(custom_names)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid custom names format"}
            )
    
    # Calculate total rows and columns from positions data
    total_rows = 1
    total_columns = 2  # Default minimum
    
    # Enforce maximum of 20 rows
    max_rows = 20
    
    if positions_data:
        max_row = 0
        max_col = 0
        for pos in positions_data:
            max_row = max(max_row, pos.get('row', 0))
            max_col = max(max_col, pos.get('column', 0))
        total_rows = min(max_row + 1, max_rows)
        total_columns = max_col + 1
    
    # Save files and record their positions
    saved_files = []
    for file in files:
        # Generate a unique filename
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = comparison_dir / unique_filename
        
        # Save the file
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        saved_files.append(unique_filename)
        
        # Find position for this file
        file_position = next((pos for pos in positions_data if pos.get('filename') == file.filename), None)
        row = file_position.get('row', 0) if file_position else 0
        column = file_position.get('column', 0) if file_position else 0
        
        # Store position in database
        store_image_position(comparison_id, unique_filename, row, column)
        
        # Store metadata
        image_size = os.path.getsize(file_path)
        store_image_metadata(comparison_id, unique_filename, file.filename, f"{image_size} bytes")
        
        # Apply custom name if provided
        if file.filename in custom_names_data:
            update_image_custom_name(comparison_id, unique_filename, custom_names_data[file.filename])
    
    # Create comparison record
    metadata = {
        "total_rows": total_rows,
        "total_columns": total_columns,
    }
    
    create_comparison(
        comparison_id=comparison_id,
        name=name,
        show_name=show_name,
        tags=tag_list,
        metadata=metadata
    )
    
    return JSONResponse(content={"comparison_id": comparison_id})

@app.get("/compare/{comparison_id}")
async def view_comparison(request: Request, comparison_id: str):
    """
    View a comparison by its ID.
    
    Retrieves the comparison data, updates the last accessed timestamp,
    and renders the comparison template with all necessary data.
    """
    # Update last accessed timestamp
    update_last_accessed(comparison_id)
    
    # Get comparison data
    comparison = get_comparison(comparison_id)
    if not comparison:
        return JSONResponse(
            status_code=404,
            content={"error": "Comparison not found"}
        )
    
    # Get image positions
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''
        SELECT ip.filename, ip.row_number, ip.column_position, 
               im.original_filename, im.image_size, im.custom_name
        FROM image_positions ip
        LEFT JOIN image_metadata im ON ip.comparison_id = im.comparison_id AND ip.filename = im.filename
        WHERE ip.comparison_id = ?
        ORDER BY ip.row_number, ip.column_position
    ''', (comparison_id,))
    
    images = []
    image_names = []
    image_sizes = []
    
    for row in c.fetchall():
        images.append(f"{comparison_id}/{row['filename']}")
        # Use custom name if available, otherwise use original filename
        image_names.append(row['custom_name'] or row['original_filename'])
        image_sizes.append(row['image_size'])
    
    conn.close()
    
    # Calculate expiration date
    expiration_date = datetime.now() + timedelta(days=comparison.get('expiration_days', 7))
    
    # Calculate the number of rows to show in dropdown (max 20)
    dropdown_rows = min(comparison.get('total_rows', 1), 20)
    
    return templates.TemplateResponse("compare.html", {
        "request": request, "images": images, "metadata": comparison, 
        "total_rows": comparison.get('total_rows', 1), "total_columns": comparison.get('total_columns', 2),
        "image_names": image_names, "image_sizes": image_sizes, "expiration_date": expiration_date.strftime('%Y-%m-%d'),
        "expiration_days": comparison.get('expiration_days', 7), "expiration_type": comparison.get('expiration_type', 'from_last_access'),
        "dropdown_rows": dropdown_rows
    })

@app.get("/")
async def home(request: Request):
    """Render the home page with upload form."""
    return templates.TemplateResponse("index.html", {"request": request})
