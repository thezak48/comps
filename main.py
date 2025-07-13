"""
FastAPI application for Comps.
Handles file uploads, comparison viewing, and database operations.
"""
# Standard library imports
import asyncio
import json
import logging
import os
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# Third-party imports
import aiofiles
from fastapi import FastAPI, Request, HTTPException, Form, File, UploadFile, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyCookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Local imports
import auth
from api.router import router as api_router
from database import (
    create_comparison,
    delete_comparison,
    get_comparison,
    get_expired_comparisons,
    init_db,
    store_image_metadata,
    store_image_position,
    update_image_custom_name,
    update_last_accessed,
)

# Random name generator for comparisons
def generate_random_name():
    """
    Generate a random, memorable name for a comparison when the user doesn't provide one.
    Format: [Adjective] [Noun]
    """
    adjectives = [
        "Amazing", "Brilliant", "Curious", "Dazzling", "Elegant", "Fantastic", 
        "Graceful", "Harmonious", "Incredible", "Jubilant", "Keen", "Luminous", 
        "Majestic", "Noble", "Optimistic", "Peaceful", "Quaint", "Radiant", 
        "Serene", "Tranquil", "Unique", "Vibrant", "Wonderful", "Zealous"
    ]

    nouns = [
        "Aurora", "Breeze", "Cascade", "Diamond", "Echo", "Fountain", "Galaxy", 
        "Horizon", "Island", "Journey", "Kaleidoscope", "Lagoon", "Mountain", 
        "Nebula", "Ocean", "Panorama", "Quest", "Rainbow", "Sunset", "Treasure", 
        "Universe", "Valley", "Waterfall", "Zenith"
    ]

    adjective = random.choice(adjectives)
    noun = random.choice(nouns)

    return f"{adjective} {noun}"

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
cookie_sec = APIKeyCookie(name="session")

# Store background tasks to prevent premature garbage collection
background_tasks = set()

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
    """Generate a custom OpenAPI schema."""
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
    """Serve the custom Swagger UI HTML page."""
    return templates.TemplateResponse(
        "swagger_ui.html", {"request": Request(scope={"type": "http"})}
    )

# Serve OpenAPI schema
@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    """Serve the OpenAPI schema as a JSON response."""
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
                logger.info("Starting cleanup of comparisons older than %s days", RETENTION_DAYS)
                try:
                    expired_ids = get_expired_comparisons(RETENTION_DAYS)

                    if expired_ids:
                        logger.info("Found %s expired comparisons to delete", len(expired_ids))
                        for comparison_id in expired_ids:
                            try:
                                logger.info("Deleting comparison %s", comparison_id)
                                delete_comparison(comparison_id, UPLOADS_PATH)
                            except OSError as e:
                                logger.error(
                                    "Error deleting comparison %s: %s", comparison_id, str(e)
                                )
                    else:
                        logger.info("No expired comparisons found")
                except sqlite3.OperationalError as e:
                    if "no such column" in str(e):
                        logger.warning(
                            "Skipping cleanup: %s. Migrations may not be complete.", str(e)
                        )
                    else:
                        logger.error("Error in cleanup task: %s", str(e))
            else:
                logger.info("Skipping cleanup: last_accessed column not found in database")

            # Run once a day
            await asyncio.sleep(86400)  # 24 hours in seconds
        except (sqlite3.Error, OSError) as e:
            logger.error("Error in cleanup task: %s", str(e))
            # If there's an error, wait a bit before trying again
            await asyncio.sleep(3600)  # 1 hour in seconds

@app.on_event("startup")
async def start_cleanup_task():
    """Start the background cleanup task when the application starts"""
    task = asyncio.create_task(cleanup_old_comparisons())
    # Add task to the set of background tasks
    background_tasks.add(task)

    # Check if database migrations are complete
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Check if the migrations table exists and has entries
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'")
        if not c.fetchone():
            logger.warning(
                "Migrations table does not exist. Database may not be properly initialized."
            )
        else:
            # Check if last_accessed column exists in comparisons table
            c.execute("PRAGMA table_info(comparisons)")
            columns = [col[1] for col in c.fetchall()]
            if 'last_accessed' not in columns:
                logger.warning(
                    "Database schema is missing expected columns. Migrations may not be complete."
                )
                logger.warning(
                    "The application may not function correctly until migrations are completed."
                )

        logger.info("Database initialized successfully")

        conn.close()
    except sqlite3.Error as e:
        logger.error("Error checking database state: %s", str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

@app.get("/login")
async def login_page(request: Request):
    """Render the login page"""
    # Check if user is already logged in
    user = await auth.get_optional_user(request)
    if user:
        return RedirectResponse(url="/")

    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request):
    """Handle login form submission"""
    form_data = await request.form()
    username = form_data.get("username")
    invitation_code = form_data.get("invitation_code")

    if not username or not invitation_code:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Username and invitation code are required"}
        )

    # Try to authenticate
    user = auth.authenticate_user(username, invitation_code)

    if not user:
        # If authentication fails, try to register (if the invitation code is valid)
        user = auth.register_user(username, invitation_code)
        if not user:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid username or invitation code"}
            )

    # Create access token
    access_token = auth.create_access_token({"sub": str(user["id"])})
    logger.info("User %s logged in successfully", user["username"])

    # Create response with cookie
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="session",
        value=access_token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 1 week
        samesite="lax"
    )

    return response

@app.get("/logout")
async def logout():
    """Log out the current user"""
    response = RedirectResponse(url="/")
    response.delete_cookie(key="session")
    return response

@app.get("/admin")
async def admin_page(request: Request):
    """Admin page for managing invitation codes"""
    user = await auth.get_optional_user(request)
    if not user or not auth.is_admin(user):
        return RedirectResponse(url="/")

    invitation_codes = auth.get_user_invitation_codes(user["id"])

    all_users = []
    if auth.is_super_admin(user):
        all_users = auth.get_all_users()

    context = {
        "request": request,
        "user": user,
        "invitation_codes": invitation_codes,
        "all_users": all_users
    }
    return templates.TemplateResponse("admin.html", context)

@app.post("/admin/create-invitation")
async def create_invitation(request: Request):
    """Create a new invitation code"""
    # Get current user
    user = await auth.get_optional_user(request)

    # Check if user is admin
    if not user or not auth.is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Create a new invitation code
    auth.create_invitation_code(user["id"])

    # Redirect back to admin page
    return RedirectResponse(url="/admin", status_code=303)

class UserAdminUpdate(BaseModel):
    """Pydantic model for updating a user's admin status."""
    user_id: int
    is_admin: bool

@app.post("/admin/user/set-admin")
async def set_user_admin_status(request: Request, update: UserAdminUpdate):
    """Set a user's admin status (super admin only)"""
    current_user = await auth.get_optional_user(request)
    if not current_user or not auth.is_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    auth.set_admin_status(update.user_id, update.is_admin)
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/account")
async def account_page(request: Request):
    """User account page"""
    # Get current user
    user = await auth.get_optional_user(request)

    # Check if user is logged in
    if not user:
        return RedirectResponse(url="/login")

    # Get user's comparisons
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        SELECT id, name, show_name, created_at, last_accessed, never_expire
        FROM comparisons
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user["id"],))

    columns = ['id', 'name', 'show_name', 'created_at', 'last_accessed', 'never_expire']
    comparisons = [dict(zip(columns, row)) for row in c.fetchall()]

    conn.close()

    return templates.TemplateResponse(
        "account.html", 
        {"request": request, "user": user, "comparisons": comparisons}
    )

@app.delete("/api/delete-comparison/{comparison_id}")
async def delete_user_comparison(comparison_id: str, request: Request):
    """Delete a comparison owned by the current user"""
    # Get current user
    user = await auth.get_optional_user(request)

    # Check if user is logged in
    if not user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    # Check if the comparison exists and belongs to the user
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_id FROM comparisons WHERE id = ?', (comparison_id,))
    result = c.fetchone()
    conn.close()

    if not result or result[0] != user["id"]:
        return JSONResponse(
            status_code=403,
            content={"error": "You don't have permission to delete this comparison"}
        )

    # Delete the comparison
    try:
        delete_comparison(comparison_id, UPLOADS_PATH)
    except OSError as e:
        logger.error("Error deleting comparison %s files: %s", comparison_id, e)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to delete comparison files."}
        )
    return JSONResponse(content={"message": "Comparison deleted successfully"})

@app.post("/api/comparison")
async def api_create_comparison(
    request: Request,
    name: str = Form(...),
    show_name: Optional[str] = Form(None),
    expiration_type: str = Form("from_last_access"),
    expiration_enabled: Optional[str] = Form(None),
    expiration_days: int = Form(7),
    tags: Optional[str] = Form(None),
    total_rows: int = Form(1),
    total_columns: int = Form(2)
):
    """
    Creates a new comparison record and returns its ID.
    This endpoint does not accept files.
    """
    logger.info("Received request to create a new comparison")
    user = await auth.get_optional_user(request)
    user_id = user["id"] if user else None
    logger.info(
        "Create comparison request from user: %s",
        user['username'] if user else 'anonymous'
    )

    comparison_id = str(uuid.uuid4())

    if not name or name.strip() == '':
        name = generate_random_name()
        logger.info("No name provided, generated random name: %s", name)

    tag_list = []
    if tags and tags.strip():
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]

    never_expire = None
    if user:
        if expiration_enabled == "true":
            never_expire = False
        else:
            never_expire = True

    metadata = {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "expiration_type": expiration_type,
        "expiration_days": expiration_days,
        "never_expire": never_expire
    }

    create_comparison(
        comparison_id=comparison_id,
        name=name,
        show_name=show_name,
        tags=tag_list,
        metadata=metadata,
        user_id=user_id
    )

    return JSONResponse(content={"comparison_id": comparison_id})


@app.post("/api/comparison/{comparison_id}/image")
async def api_upload_image(
    comparison_id: str,
    file: UploadFile = File(...),
    row: int = Form(...),
    column: int = Form(...),
    original_filename: str = Form(...),
    custom_name: Optional[str] = Form(None)
):
    """
    Uploads a single image to an existing comparison.
    """
    logger.info(
        "Uploading image %s to comparison %s at (%s, %s)",
        original_filename, comparison_id, row, column
    )

    comparison = get_comparison(comparison_id)
    if not comparison:
        return JSONResponse(status_code=404, content={"error": "Comparison not found"})

    comparison_dir = Path(UPLOADS_PATH) / comparison_id
    comparison_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = comparison_dir / unique_filename

    async with aiofiles.open(file_path, "wb") as buffer:
        await buffer.write(await file.read())

    store_image_position(comparison_id, unique_filename, row, column)

    image_size = os.path.getsize(file_path)
    store_image_metadata(comparison_id, unique_filename, original_filename, f"{image_size} bytes")

    if custom_name:
        update_image_custom_name(comparison_id, unique_filename, custom_name)

    return JSONResponse(
        content={"filename": unique_filename, "message": "Image uploaded successfully"}
    )


@app.post("/upload/")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    name: str = Form(...),
    show_name: Optional[str] = Form(None),
    expiration_type: str = Form("from_last_access"),
    expiration_enabled: Optional[str] = Form(None),
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
    logger.info("Received upload request with %s files", len(files))

    # Get current user if logged in
    user = None
    if request:
        user = await auth.get_optional_user(request)
        logger.info(
            "Upload request from user: %s", user['username'] if user else 'anonymous'
        )

    # Generate a unique ID for this comparison
    comparison_id = str(uuid.uuid4())

    # Generate a random name if none provided
    if not name or name.strip() == '':
        name = generate_random_name()
        logger.info("No name provided, generated random name: %s", name)

    # Create directory for this comparison
    comparison_dir = Path(UPLOADS_PATH) / comparison_id
    comparison_dir.mkdir(parents=True, exist_ok=True)

    # Process tags
    tag_list = []
    if tags and tags.strip():
        # Split tags by comma and remove whitespace
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
        if not isinstance(positions_data, list):
            return JSONResponse(
                status_code=400,
                content={"error": "file_positions must be a list of objects"}
            )
        max_row = 0
        max_col = 0
        for pos in positions_data:
            if isinstance(pos, dict):
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
        async with aiofiles.open(file_path, "wb") as buffer:
            await buffer.write(await file.read())

        saved_files.append(unique_filename)

        # Find position for this file
        file_position = None
        if isinstance(positions_data, list):
            file_position = next(
                (
                    pos for pos in positions_data
                    if isinstance(pos, dict) and pos.get('filename') == file.filename
                ),
                None
            )

        row = file_position.get('row', 0) if file_position else 0
        column = file_position.get('column', 0) if file_position else 0

        # Store position in database
        store_image_position(comparison_id, unique_filename, row, column)

        # Store metadata
        image_size = os.path.getsize(file_path)
        store_image_metadata(comparison_id, unique_filename, file.filename, f"{image_size} bytes")

        # Apply custom name if provided
        if file.filename in custom_names_data:
            update_image_custom_name(
                comparison_id, unique_filename, custom_names_data[file.filename]
            )

    # Determine if this comparison should never expire
    never_expire = None
    if user:
        # For logged-in users, check if expiration was explicitly enabled
        if expiration_enabled == "true":
            never_expire = False
        else:
            never_expire = True

    # Create comparison record
    metadata = {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "expiration_type": expiration_type,
        "expiration_days": expiration_days,
        "never_expire": never_expire
    }

    create_comparison(
        comparison_id=comparison_id,
        name=name,
        show_name=show_name,
        tags=tag_list,
        metadata=metadata,
        user_id=user["id"] if user else None
    )

    return JSONResponse(content={"comparison_id": comparison_id})

@app.get("/compare/{comparison_id}")
async def view_comparison(request: Request, comparison_id: str):
    """
    View a comparison by its ID.
    
    Retrieves the comparison data, updates the last accessed timestamp,
    and renders the comparison template with all necessary data.
    """
    # Get current user if logged in
    user = await auth.get_optional_user(request)

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
    never_expires = comparison.get('never_expire', False)

    # Calculate the number of rows to show in dropdown (max 20)
    dropdown_rows = min(comparison.get('total_rows', 1), 20)

    context = {
        "request": request,
        "user": user,
        "images": images,
        "metadata": comparison,
        "total_rows": comparison.get('total_rows', 1),
        "total_columns": comparison.get('total_columns', 2),
        "image_names": image_names,
        "image_sizes": image_sizes,
        "expiration_date": expiration_date.strftime('%Y-%m-%d'),
        "expiration_days": comparison.get('expiration_days', 7), 
        "expiration_type": comparison.get('expiration_type', 'from_last_access'), 
        "never_expire": never_expires,
        "dropdown_rows": dropdown_rows
    }

    return templates.TemplateResponse("compare.html", context)

@app.get("/")
async def home(request: Request):
    """Render the home page with upload form."""
    user = await auth.get_optional_user(request)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})
