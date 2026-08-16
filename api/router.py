import hashlib
import logging
import os
import random
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyCookie, OAuth2PasswordRequestForm

import auth
from database import (
    create_comparison,
    delete_comparison,
    get_comparison,
    get_comparison_edit_token,
    set_comparison_edit_token,
    store_image_metadata,
    store_image_position,
    update_image_custom_name,
    update_last_accessed,
)
from db import query, query_dicts
from storage import create_comparison_storage, save_upload_file

from .models import (
    ComparisonCreate,
    ComparisonCreateResponse,
    ComparisonDetail,
    ComparisonResponse,
    CustomNameUpdate,
    ExpirationDays,
    ExpirationType,
)

router = APIRouter(prefix="/api/v1", tags=["api"])

MAX_ROWS = 200

EDIT_TOKEN_HEADER = "X-Edit-Token"

# How long an ownerless comparison stays writable after creation. The browser holds
# the token only for the duration of the upload, so this bounds the capability
# server-side rather than relying on the client having discarded it.
EDIT_TOKEN_TTL_SECONDS = int(os.getenv("EDIT_TOKEN_TTL_SECONDS", str(24 * 60 * 60)))

logger = logging.getLogger(__name__)
cookie_sec = APIKeyCookie(name="session")


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


def _hash_edit_token(token: str) -> str:
    """Hash an edit token for storage. Tokens are high-entropy, so a plain digest suffices."""
    return hashlib.sha256(token.encode()).hexdigest()


def _issue_edit_token(comparison_id: str) -> str:
    """Generate an edit token for a comparison and persist only its hash and expiry."""
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + EDIT_TOKEN_TTL_SECONDS
    set_comparison_edit_token(comparison_id, _hash_edit_token(token), expires_at)
    return token


def _authorize_comparison_write(
    request: Request, comparison_id: str, comparison: dict, user: Optional[dict]
):
    """Authorize a write to a comparison.

    An owned comparison is gated by ownership. An ownerless one has no owner to
    check, so it is gated by the edit token issued at creation, which the creator
    holds only for the duration of the upload.
    """
    auth.require_comparison_write_access(comparison, user)
    if comparison.get("user_id") is not None:
        return

    supplied = request.headers.get(EDIT_TOKEN_HEADER)
    stored, expires_at = get_comparison_edit_token(comparison_id)
    if supplied and stored and secrets.compare_digest(_hash_edit_token(supplied), stored):
        # A token issued before this column existed has no expiry recorded; treat it
        # as expired rather than granting an unbounded capability.
        if expires_at is not None and int(time.time()) <= expires_at:
            return

    raise HTTPException(status_code=403, detail="Not authorized to modify this comparison")


@router.post("/login")
async def api_login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate and get an access token for API usage.
    - **username**: Your username
    - **password**: Your invitation code
    """
    user = auth.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or invitation code",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": str(user["id"])})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/comparisons", response_model=List[ComparisonResponse])
async def list_comparisons(request: Request):
    """
    List comparisons visible to the authenticated caller.

    Regular users receive their own comparisons. Admins receive all of them.

    Returns a list of comparisons with their basic metadata including:
    - ID, name, and show name
    - Tags
    - Grid dimensions (rows and columns)
    - Expiration settings
    - Creation and last accessed timestamps
    """
    user = await auth.get_optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    columns = (
        "SELECT id, name, show_name, total_rows, total_columns, "
        "expiration_type, expiration_days, created_at, last_accessed "
        "FROM comparisons"
    )
    if auth.is_admin(user):
        rows = query_dicts(f"{columns} ORDER BY created_at DESC")
    else:
        rows = query_dicts(f"{columns} WHERE user_id = ? ORDER BY created_at DESC", (user["id"],))
    comparisons = []
    for row in rows:
        comparison_id = row["id"]
        tag_rows = query("SELECT tag FROM tags WHERE comparison_id = ?", (comparison_id,))
        tags = [t[0] for t in tag_rows]
        row["tags"] = tags
        # Normalize datetime fields to strings for response model compatibility
        ca = row.get("created_at")
        la = row.get("last_accessed")
        if isinstance(ca, datetime):
            row["created_at"] = ca.strftime("%Y-%m-%d %H:%M:%S")
        elif ca is not None:
            row["created_at"] = str(ca)
        if isinstance(la, datetime):
            row["last_accessed"] = la.strftime("%Y-%m-%d %H:%M:%S")
        elif la is not None:
            row["last_accessed"] = str(la)
        comparisons.append(row)
    return comparisons


@router.post("/comparisons", response_model=ComparisonCreateResponse, status_code=201)
async def create_new_comparison(
    comparison_data: ComparisonCreate,
    user: Optional[dict] = Depends(auth.get_optional_user),
):
    """
    Create a new comparison.

    Creates a new comparison with the specified parameters:
    - Name and show name (optional)
    - Tags for categorization (optional)
    - Grid dimensions (rows and columns, max 20 rows)
    - Expiration settings
    """
    comparison_id = str(uuid.uuid4())

    # Use a random name if none is provided
    name = comparison_data.name or generate_random_name()

    # Get user ID if a user is authenticated
    user_id = user["id"] if user else None

    # Prepare metadata, enforcing maximum rows limit
    metadata = {
        "total_columns": comparison_data.total_columns,
        "total_rows": min(comparison_data.total_rows, MAX_ROWS),
        "expiration_type": comparison_data.expiration_type,
        "expiration_days": comparison_data.expiration_days,
        "never_expire": auth.comparison_never_expires(user),
    }

    create_comparison_storage(comparison_id)

    # Store in database
    create_comparison(
        comparison_id=comparison_id,
        name=name,
        show_name=comparison_data.show_name,
        tags=comparison_data.tags,
        metadata=metadata,
        user_id=user_id,
    )

    # An ownerless comparison has no owner to authorize later writes, so issue a token.
    edit_token = _issue_edit_token(comparison_id) if user_id is None else None

    # Return the response
    return ComparisonCreateResponse(
        id=comparison_id,
        name=name,
        show_name=comparison_data.show_name,
        tags=comparison_data.tags,
        total_rows=metadata["total_rows"],
        total_columns=metadata["total_columns"],
        expiration_type=metadata.get("expiration_type", "from_last_access"),
        expiration_days=int(metadata.get("expiration_days", 7)),
        created_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        last_accessed=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        edit_token=edit_token,
    )


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
    rows = query(
        """
        SELECT ip.filename, ip.column_position, ip.row_number,
               im.original_filename, im.image_size, im.custom_name
        FROM image_positions ip
        LEFT JOIN image_metadata im
            ON ip.comparison_id = im.comparison_id
            AND ip.filename = im.filename
        WHERE ip.comparison_id = ?
        ORDER BY ip.row_number ASC, ip.column_position ASC
        """,
        (comparison_id,),
    )

    images = []
    for row in rows:
        filename, column, row_num, original_filename, image_size, custom_name = row
        images.append(
            {
                "filename": filename,
                "original_filename": original_filename,
                "custom_name": custom_name,
                "image_size": image_size,
                "row": row_num,
                "column": column,
            }
        )

    # Add images to the response
    comparison_data["images"] = images
    return comparison_data


@router.put("/comparisons/{comparison_id}/images/{filename}", status_code=200)
async def update_image_metadata(
    request: Request,
    comparison_id: str,
    filename: str,
    update_data: CustomNameUpdate,
    user: Optional[dict] = Depends(auth.get_optional_user),
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
    _authorize_comparison_write(request, comparison_id, comparison_data, user)

    # Check if file exists
    rows = query(
        "SELECT filename FROM image_metadata WHERE comparison_id = ? AND filename = ?",
        (comparison_id, filename),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Image not found")

    # Update custom name
    update_image_custom_name(comparison_id, filename, update_data.custom_name)

    return {"message": "Image metadata updated successfully"}


@router.delete("/delete-comparison/{comparison_id}")
async def delete_user_comparison(comparison_id: str, request: Request):
    """Delete a comparison owned by the current user"""
    # Get current user
    user = await auth.get_optional_user(request)

    # Check if user is logged in
    if not user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    # Check if the comparison exists and belongs to the user
    rows = query("SELECT user_id FROM comparisons WHERE id = ?", (comparison_id,))
    result = rows[0] if rows else None

    if not result or result[0] != user["id"]:
        return JSONResponse(
            status_code=403,
            content={"error": "You don't have permission to delete this comparison"},
        )

    # Delete the comparison
    try:
        delete_comparison(comparison_id)
    except OSError as e:
        logger.error("Error deleting comparison %s files: %s", comparison_id, e)
        return JSONResponse(
            status_code=500, content={"error": "Failed to delete comparison files."}
        )
    return JSONResponse(content={"message": "Comparison deleted successfully"})


@router.post("/comparison")
async def api_create_comparison(
    request: Request,
    name: Optional[str] = Form(None),
    show_name: Optional[str] = Form(None),
    expiration_type: ExpirationType = Form("from_last_access"),
    expiration_enabled: bool = Form(False),
    expiration_days: ExpirationDays = Form(7),
    tags: Optional[str] = Form(None),
    total_rows: int = Form(1),
    total_columns: int = Form(2),
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
        user["username"] if user else "anonymous",
    )

    comparison_id = str(uuid.uuid4())

    if not name or name.strip() == "":
        name = generate_random_name()
        logger.info("No name provided, generated random name: %s", name)

    tag_list = []
    if tags and tags.strip():
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

    never_expire = auth.comparison_never_expires(user, expiration_enabled)

    metadata = {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "expiration_type": expiration_type,
        "expiration_days": expiration_days,
        "never_expire": never_expire,
    }

    create_comparison(
        comparison_id=comparison_id,
        name=name,
        show_name=show_name,
        tags=tag_list,
        metadata=metadata,
        user_id=user_id,
    )

    response_body = {"comparison_id": comparison_id}
    # An ownerless comparison has no owner to authorize later writes, so issue a token.
    if user_id is None:
        response_body["edit_token"] = _issue_edit_token(comparison_id)

    return JSONResponse(content=response_body)


@router.post("/comparison/{comparison_id}/image")
async def api_upload_image(
    request: Request,
    comparison_id: str,
    file: UploadFile = File(...),
    row: int = Form(...),
    column: int = Form(...),
    original_filename: str = Form(...),
    custom_name: Optional[str] = Form(None),
    user: Optional[dict] = Depends(auth.get_optional_user),
):
    """
    Uploads a single image to an existing comparison.
    """
    logger.info(
        "Uploading image %s to comparison %s at (%s, %s)",
        original_filename,
        comparison_id,
        row,
        column,
    )

    comparison = get_comparison(comparison_id)
    if not comparison:
        return JSONResponse(status_code=404, content={"error": "Comparison not found"})
    _authorize_comparison_write(request, comparison_id, comparison, user)

    safe_name = file.filename or ""
    file_ext = Path(safe_name).suffix
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    try:
        image_size = await save_upload_file(comparison_id, unique_filename, file)
    except OSError:
        logger.exception("Error storing uploaded image")
        return JSONResponse(status_code=500, content={"error": "Failed to store uploaded image"})

    store_image_position(comparison_id, unique_filename, row, column)

    store_image_metadata(comparison_id, unique_filename, original_filename, f"{image_size} bytes")

    if custom_name:
        update_image_custom_name(comparison_id, unique_filename, custom_name)

    return JSONResponse(
        content={"filename": unique_filename, "message": "Image uploaded successfully"}
    )
