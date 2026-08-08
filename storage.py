import mimetypes
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
UPLOADS_PATH = os.getenv("UPLOADS_PATH", "uploads")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "").strip()
S3_REGION = os.getenv("S3_REGION")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_KEY_PREFIX = os.getenv("S3_KEY_PREFIX", "").strip().strip("/")
S3_PUBLIC_BASE_URL = os.getenv("S3_PUBLIC_BASE_URL", "").strip().rstrip("/")
S3_PRESIGNED_URL_TTL_SECONDS = int(os.getenv("S3_PRESIGNED_URL_TTL_SECONDS", "3600"))
S3_PRESIGNED_URL_CACHE_MAX_SIZE = int(os.getenv("S3_PRESIGNED_URL_CACHE_MAX_SIZE", "10000"))

_s3_client = None
_presigned_url_cache: dict[str, tuple[str, float]] = {}
_presigned_url_cache_lock = threading.Lock()
_PRESIGNED_URL_REFRESH_SKEW_SECONDS = 5


def is_s3_enabled() -> bool:
    return STORAGE_BACKEND == "s3"


def ensure_storage_ready():
    if is_s3_enabled():
        if not S3_BUCKET_NAME:
            raise RuntimeError("S3_BUCKET_NAME must be set when STORAGE_BACKEND is 's3'")
        # Fail fast if credentials or endpoint are invalid.
        try:
            _get_s3_client().head_bucket(Bucket=S3_BUCKET_NAME)
        except (ClientError, BotoCoreError) as exc:
            raise RuntimeError(
                f"Unable to access configured S3 bucket '{S3_BUCKET_NAME}'. "
                "Check bucket name, credentials, and permissions."
            ) from exc
        return
    Path(UPLOADS_PATH).mkdir(parents=True, exist_ok=True)


def create_comparison_storage(comparison_id: str):
    if is_s3_enabled():
        return
    safe_comparison_id = _normalize_comparison_id(comparison_id)
    (Path(UPLOADS_PATH) / safe_comparison_id).mkdir(parents=True, exist_ok=True)


async def save_upload_file(comparison_id: str, filename: str, file: UploadFile) -> int:
    safe_comparison_id = _normalize_comparison_id(comparison_id)
    safe_filename = _normalize_filename(filename)
    await file.seek(0)
    content_type = (
        file.content_type or mimetypes.guess_type(safe_filename)[0] or "application/octet-stream"
    )

    if is_s3_enabled():
        key = _get_object_key(safe_comparison_id, safe_filename)
        _evict_presigned_url_cache(keys=[key])
        try:
            client = _get_s3_client()
            await run_in_threadpool(
                client.upload_fileobj,
                file.file,
                S3_BUCKET_NAME,
                key,
                {"ContentType": content_type},
            )
            head = client.head_object(Bucket=S3_BUCKET_NAME, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise OSError(f"Failed to upload {safe_filename} to S3: {exc}") from exc
        return int(head.get("ContentLength", 0))

    comparison_dir = Path(UPLOADS_PATH) / safe_comparison_id
    comparison_dir.mkdir(parents=True, exist_ok=True)
    file_path = comparison_dir / safe_filename
    bytes_written = 0
    async with aiofiles.open(file_path, "wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            bytes_written += len(chunk)
            await buffer.write(chunk)
    return bytes_written


def get_presigned_image_url(comparison_id: str, filename: str) -> str:
    safe_comparison_id = _normalize_comparison_id(comparison_id)
    safe_filename = _normalize_filename(filename)
    key = _get_object_key(safe_comparison_id, safe_filename)
    cached_url = _get_cached_presigned_url(key)
    if cached_url:
        return cached_url

    try:
        client = _get_s3_client()
        client.head_object(Bucket=S3_BUCKET_NAME, Key=key)
        expires_in = max(1, S3_PRESIGNED_URL_TTL_SECONDS)
        presigned_url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
        _cache_presigned_url(key, presigned_url, expires_in)
        return presigned_url
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            raise FileNotFoundError(
                f"Image not found: {safe_comparison_id}/{safe_filename}"
            ) from exc
        raise OSError(f"Failed to generate S3 URL for {safe_filename}: {exc}") from exc
    except BotoCoreError as exc:
        raise OSError(f"Failed to generate S3 URL for {safe_filename}: {exc}") from exc


def get_browser_image_url(comparison_id: str, filename: str) -> str:
    safe_comparison_id = _normalize_comparison_id(comparison_id)
    safe_filename = _normalize_filename(filename)
    key = _get_object_key(safe_comparison_id, safe_filename)

    if S3_PUBLIC_BASE_URL:
        return f"{S3_PUBLIC_BASE_URL}/{key}"

    if is_s3_enabled():
        return f"/uploads/{safe_comparison_id}/{safe_filename}"

    return f"/uploads/{safe_comparison_id}/{safe_filename}"


def delete_comparison_assets(
    comparison_id: str,
    uploads_path: Optional[str] = None,
    filenames: Optional[list[str]] = None,
):
    safe_comparison_id = _normalize_comparison_id(comparison_id)
    if is_s3_enabled():
        client = _get_s3_client()
        if filenames is not None:
            if not filenames:
                return
            keys = [
                _get_object_key(safe_comparison_id, _normalize_filename(filename))
                for filename in filenames
            ]
            _evict_presigned_url_cache(keys=keys)
            _delete_s3_keys(client, keys)
            return

        prefix = _get_object_key_prefix(safe_comparison_id)
        _evict_presigned_url_cache(prefix=prefix)
        keys = []
        continuation_token = None
        try:
            while True:
                list_kwargs = {"Bucket": S3_BUCKET_NAME, "Prefix": prefix}
                if continuation_token:
                    list_kwargs["ContinuationToken"] = continuation_token
                response = client.list_objects_v2(**list_kwargs)
                keys.extend(obj["Key"] for obj in response.get("Contents", []))
                if not response.get("IsTruncated"):
                    break
                continuation_token = response.get("NextContinuationToken")
        except (ClientError, BotoCoreError) as exc:
            raise OSError(
                f"Failed to list S3 objects for comparison {safe_comparison_id}: {exc}"
            ) from exc

        _delete_s3_keys(client, keys)
        return

    base_uploads_path = uploads_path or UPLOADS_PATH
    comparison_dir = os.path.join(base_uploads_path, safe_comparison_id)
    if os.path.exists(comparison_dir):
        shutil.rmtree(comparison_dir)


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=S3_REGION or None,
            endpoint_url=S3_ENDPOINT_URL or None,
        )
    return _s3_client


def _get_object_key(comparison_id: str, filename: str) -> str:
    base_key = f"{comparison_id}/{filename}"
    if not S3_KEY_PREFIX:
        return base_key
    return f"{S3_KEY_PREFIX}/{base_key}"


def _get_object_key_prefix(comparison_id: str) -> str:
    return _get_object_key(comparison_id, "")


def _delete_s3_keys(client, keys: list[str]):
    for start in range(0, len(keys), 1000):
        chunk = keys[start : start + 1000]
        if not chunk:
            continue
        try:
            response = client.delete_objects(
                Bucket=S3_BUCKET_NAME,
                Delete={"Objects": [{"Key": key} for key in chunk]},
            )
        except (ClientError, BotoCoreError) as exc:
            raise OSError(f"Failed to delete objects from S3: {exc}") from exc

        errors = response.get("Errors", [])
        if errors:
            details = "; ".join(
                (
                    f"{err.get('Key', 'unknown')}: {err.get('Code', 'Unknown')} "
                    f"{err.get('Message', '')}"
                ).strip()
                for err in errors
            )
            raise OSError(f"S3 reported delete errors: {details}")


def _get_cached_presigned_url(key: str) -> Optional[str]:
    now = time.monotonic()
    with _presigned_url_cache_lock:
        cached = _presigned_url_cache.get(key)
        if not cached:
            return None

        cached_url, expires_at = cached
        if expires_at - _PRESIGNED_URL_REFRESH_SKEW_SECONDS <= now:
            _presigned_url_cache.pop(key, None)
            return None

        return cached_url


def _cache_presigned_url(key: str, url: str, expires_in: int):
    now = time.monotonic()
    expires_at = now + max(1, expires_in)
    with _presigned_url_cache_lock:
        _prune_presigned_url_cache(now)
        _presigned_url_cache[key] = (url, expires_at)

        # Keep cache bounded to avoid unbounded memory growth.
        max_size = max(1, S3_PRESIGNED_URL_CACHE_MAX_SIZE)
        while len(_presigned_url_cache) > max_size:
            oldest_key = next(iter(_presigned_url_cache))
            _presigned_url_cache.pop(oldest_key, None)


def _evict_presigned_url_cache(
    keys: Optional[list[str]] = None,
    prefix: Optional[str] = None,
):
    with _presigned_url_cache_lock:
        if keys:
            for key in keys:
                _presigned_url_cache.pop(key, None)

        if prefix:
            for key in list(_presigned_url_cache):
                if key.startswith(prefix):
                    _presigned_url_cache.pop(key, None)


def _prune_presigned_url_cache(now: float):
    for cache_key, (_, expires_at) in list(_presigned_url_cache.items()):
        if expires_at - _PRESIGNED_URL_REFRESH_SKEW_SECONDS <= now:
            _presigned_url_cache.pop(cache_key, None)


def _normalize_comparison_id(comparison_id: str) -> str:
    try:
        return str(uuid.UUID(str(comparison_id)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise OSError("Invalid comparison ID format") from exc


def _normalize_filename(filename: str) -> str:
    if not isinstance(filename, str):
        raise OSError("Invalid filename format")

    normalized = filename.strip()
    if not normalized or normalized in {".", ".."}:
        raise OSError("Invalid filename format")

    basename = os.path.basename(normalized)
    if basename != normalized:
        raise OSError("Invalid filename format")

    if "/" in normalized or "\\" in normalized:
        raise OSError("Invalid filename format")

    return basename
