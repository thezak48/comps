"""
FastAPI application for Comps.
Handles file uploads, comparison viewing, and database operations.
"""

# Standard library imports
import asyncio
import logging
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import APIKeyCookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import auth
from api.router import router as api_router
from database import (
    delete_comparison,
    get_comparison,
    get_expired_comparisons,
    get_user_comparisons,
    init_db,
    update_last_accessed,
)
from database_metrics import get_metrics
from db import backend_name, connect, query_dicts


# Random name generator for comparisons
def generate_random_name():
    """
    Generate a random, memorable name for a comparison when the user doesn't provide one.
    Format: [Adjective] [Noun]
    """
    adjectives = [
        "Amazing",
        "Brilliant",
        "Curious",
        "Dazzling",
        "Elegant",
        "Fantastic",
        "Graceful",
        "Harmonious",
        "Incredible",
        "Jubilant",
        "Keen",
        "Luminous",
        "Majestic",
        "Noble",
        "Optimistic",
        "Peaceful",
        "Quaint",
        "Radiant",
        "Serene",
        "Tranquil",
        "Unique",
        "Vibrant",
        "Wonderful",
        "Zealous",
    ]

    nouns = [
        "Aurora",
        "Breeze",
        "Cascade",
        "Diamond",
        "Echo",
        "Fountain",
        "Galaxy",
        "Horizon",
        "Island",
        "Journey",
        "Kaleidoscope",
        "Lagoon",
        "Mountain",
        "Nebula",
        "Ocean",
        "Panorama",
        "Quest",
        "Rainbow",
        "Sunset",
        "Treasure",
        "Universe",
        "Valley",
        "Waterfall",
        "Zenith",
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
    redoc_url=None,  # Disable default redoc
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
cookie_sec = APIKeyCookie(name="session")

# Store background tasks to prevent premature garbage collection
background_tasks = set()

# Get configuration from environment
DB_PATH = os.getenv("DB_PATH", "comparisons.db")
UPLOADS_PATH = os.getenv("UPLOADS_PATH", "uploads")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))

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
            logger.info("Starting cleanup of comparisons older than %s days", RETENTION_DAYS)
            expired_ids = get_expired_comparisons(RETENTION_DAYS)
            if expired_ids:
                logger.info("Found %s expired comparisons to delete", len(expired_ids))
                for comparison_id in expired_ids:
                    try:
                        logger.info("Deleting comparison %s", comparison_id)
                        delete_comparison(comparison_id, UPLOADS_PATH)
                    except OSError as e:
                        logger.error(
                            "Error deleting comparison %s: %s",
                            comparison_id,
                            str(e),
                        )
            else:
                logger.info("No expired comparisons found")

            # Run once a day
            await asyncio.sleep(86400)  # 24 hours in seconds
        except OSError as e:
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
    # Best-effort schema presence check
    try:
        rows = query_dicts("SELECT 1 as ok")
        logger.info("Database initialized successfully (%s)", backend_name())
    except Exception as e:
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

    return templates.TemplateResponse("login.jinja", {"request": request})


@app.post("/login")
async def login(request: Request):
    """Handle login form submission"""
    form_data = await request.form()
    username = form_data.get("username")
    invitation_code = form_data.get("invitation_code")

    if not username or not invitation_code:
        return templates.TemplateResponse(
            "login.jinja",
            {"request": request, "error": "Username and invitation code are required"},
        )

    # Try to authenticate
    user = auth.authenticate_user(username, invitation_code)

    if not user:
        # If authentication fails, try to register (if the invitation code is valid)
        user = auth.register_user(username, invitation_code)
        if not user:
            return templates.TemplateResponse(
                "login.jinja",
                {"request": request, "error": "Invalid username or invitation code"},
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
        samesite="lax",
    )

    return response


@app.get("/logout")
async def logout():
    """Log out the current user"""
    response = RedirectResponse(url="/")
    response.delete_cookie(key="session")
    return response


# Admin metrics page
@app.get("/admin/metrics", response_class=HTMLResponse)
async def admin_metrics_page(request: Request):
    user = await auth.get_optional_user(request)
    if not user or not auth.is_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    metrics = get_metrics()
    return templates.TemplateResponse(
        "metrics.jinja", {"request": request, "user": user, "metrics": metrics}
    )


@app.get("/admin", response_class=HTMLResponse)
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
        "all_users": all_users,
    }
    return templates.TemplateResponse("admin.jinja", context)


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


@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    user = await auth.get_optional_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    user_comparisons = get_user_comparisons(user["id"])
    invitation_codes = auth.get_user_invitation_codes(user["id"])
    api_keys = auth.get_user_api_keys(user["id"])

    return templates.TemplateResponse(
        "account.jinja",
        {
            "request": request,
            "user": user,
            "comparisons": user_comparisons,
            "invitation_codes": invitation_codes,
            "api_keys": api_keys,
        },
    )


@app.post("/account/api-keys/create")
async def create_api_key_endpoint(request: Request, key_name: str = Form(...)):
    user = await auth.get_optional_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    if not key_name or not key_name.strip():
        return JSONResponse(status_code=400, content={"error": "Key name cannot be empty"})

    try:
        new_key = auth.create_api_key(user["id"], key_name.strip())
        return JSONResponse(status_code=201, content={"key": new_key})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/account/api-keys/delete/{key_id}")
async def delete_api_key_endpoint(request: Request, key_id: int):
    user = await auth.get_optional_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    success = auth.delete_api_key(user["id"], key_id)
    if success:
        return JSONResponse(content={"message": "API Key deleted successfully."})
    else:
        return JSONResponse(
            status_code=404,
            content={"error": "Key not found or you do not have permission to delete it."},
        )


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
        return JSONResponse(status_code=404, content={"error": "Comparison not found"})

    # Get image positions
    rows = query_dicts(
        """
        SELECT ip.filename, ip.row_number, ip.column_position,
               im.original_filename, im.image_size, im.custom_name
        FROM image_positions ip
        LEFT JOIN image_metadata im
        ON ip.comparison_id = im.comparison_id AND ip.filename = im.filename
        WHERE ip.comparison_id = ?
        ORDER BY ip.row_number, ip.column_position
    """,
        (comparison_id,),
    )

    images = []
    image_names = []
    image_sizes = []

    for row in rows:
        images.append(f"{comparison_id}/{row['filename']}")
        # Use custom name if available, otherwise use original filename
        image_names.append(row.get("custom_name") or row.get("original_filename"))
        image_sizes.append(row.get("image_size"))

    # Calculate expiration date
    expiration_date = datetime.now() + timedelta(days=comparison.get("expiration_days", 7))
    never_expires = comparison.get("never_expire", False)

    # Calculate the number of rows to show in dropdown (max 20)
    dropdown_rows = min(comparison.get("total_rows", 1), 20)

    context = {
        "request": request,
        "user": user,
        "images": images,
        "metadata": comparison,
        "total_rows": comparison.get("total_rows", 1),
        "total_columns": comparison.get("total_columns", 2),
        "image_names": image_names,
        "image_sizes": image_sizes,
        "expiration_date": expiration_date.strftime("%Y-%m-%d"),
        "expiration_days": comparison.get("expiration_days", 7),
        "expiration_type": comparison.get("expiration_type", "from_last_access"),
        "never_expire": never_expires,
        "dropdown_rows": dropdown_rows,
    }

    return templates.TemplateResponse("compare.jinja", context)


@app.get("/")
async def home(request: Request):
    """Render the home page with upload form."""
    user = await auth.get_optional_user(request)
    return templates.TemplateResponse("index.jinja", {"request": request, "user": user})
