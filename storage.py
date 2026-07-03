import mimetypes
import os
import shutil
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
S3_PRESIGNED_URL_TTL_SECONDS = int(os.getenv("S3_PRESIGNED_URL_TTL_SECONDS", "3600"))

_s3_client = None


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
    (Path(UPLOADS_PATH) / comparison_id).mkdir(parents=True, exist_ok=True)


async def save_upload_file(comparison_id: str, filename: str, file: UploadFile) -> int:
    await file.seek(0)
    content_type = (
        file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    )

    if is_s3_enabled():
        key = _get_object_key(comparison_id, filename)
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
            raise OSError(f"Failed to upload {filename} to S3: {exc}") from exc
        await file.seek(0)
        return int(head.get("ContentLength", 0))

    comparison_dir = Path(UPLOADS_PATH) / comparison_id
    comparison_dir.mkdir(parents=True, exist_ok=True)
    file_path = comparison_dir / filename
    bytes_written = 0
    async with aiofiles.open(file_path, "wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            bytes_written += len(chunk)
            await buffer.write(chunk)
    await file.seek(0)
    return bytes_written


def get_presigned_image_url(comparison_id: str, filename: str) -> str:
    key = _get_object_key(comparison_id, filename)
    try:
        client = _get_s3_client()
        client.head_object(Bucket=S3_BUCKET_NAME, Key=key)
        expires_in = max(1, S3_PRESIGNED_URL_TTL_SECONDS)
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            raise FileNotFoundError(f"Image not found: {comparison_id}/{filename}") from exc
        raise OSError(f"Failed to generate S3 URL for {filename}: {exc}") from exc
    except BotoCoreError as exc:
        raise OSError(f"Failed to generate S3 URL for {filename}: {exc}") from exc


def delete_comparison_assets(
    comparison_id: str,
    uploads_path: Optional[str] = None,
    filenames: Optional[list[str]] = None,
):
    if is_s3_enabled():
        client = _get_s3_client()
        if filenames is not None:
            if not filenames:
                return
            keys = [_get_object_key(comparison_id, filename) for filename in filenames]
            _delete_s3_keys(client, keys)
            return

        prefix = _get_object_key_prefix(comparison_id)
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
                f"Failed to list S3 objects for comparison {comparison_id}: {exc}"
            ) from exc

        _delete_s3_keys(client, keys)
        return

    base_uploads_path = uploads_path or UPLOADS_PATH
    comparison_dir = os.path.join(base_uploads_path, comparison_id)
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
