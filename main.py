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

@app.get("/")
async def home(request: Request):
    """Render the home page with upload form."""
    return templates.TemplateResponse("index.html", {"request": request})
