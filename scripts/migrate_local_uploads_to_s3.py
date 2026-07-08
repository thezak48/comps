#!/usr/bin/env python3
"""
Migrate local uploads to S3-compatible storage and reconcile image metadata.

By default this script:
  - Reads image records from the DB (image_positions + image_metadata)
  - Uploads local files from UPLOADS_PATH/<comparison_id>/<filename> to S3
  - Updates image_metadata.image_size to "<bytes> bytes"
  - Inserts missing image_metadata rows when needed

Usage:
  python scripts/migrate_local_uploads_to_s3.py --dry-run
  python scripts/migrate_local_uploads_to_s3.py --skip-existing
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Ensure project root is on sys.path.
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db import execute, query, query_one  # noqa: E402


def _object_key(prefix: str, comparison_id: str, filename: str) -> str:
    base = f"{comparison_id}/{filename}"
    if not prefix:
        return base
    return f"{prefix}/{base}"


def _file_records() -> List[Tuple[str, str, str]]:
    rows = query("""
        SELECT DISTINCT
            ip.comparison_id,
            ip.filename,
            COALESCE(im.original_filename, ip.filename) AS original_filename
        FROM image_positions ip
        LEFT JOIN image_metadata im
          ON ip.comparison_id = im.comparison_id
         AND ip.filename = im.filename
        ORDER BY ip.comparison_id, ip.filename
        """)
    return [(str(r[0]), str(r[1]), str(r[2])) for r in rows]


def _upsert_image_metadata(
    comparison_id: str,
    filename: str,
    original_filename: str,
    image_size: str,
):
    existing = query_one(
        "SELECT id FROM image_metadata WHERE comparison_id = ? AND filename = ?",
        (comparison_id, filename),
    )
    if existing:
        execute(
            """
            UPDATE image_metadata
            SET image_size = ?,
                original_filename = COALESCE(original_filename, ?)
            WHERE comparison_id = ? AND filename = ?
            """,
            (image_size, original_filename, comparison_id, filename),
        )
    else:
        execute(
            """
            INSERT INTO image_metadata (
                comparison_id, filename, original_filename, image_size
            ) VALUES (?, ?, ?, ?)
            """,
            (comparison_id, filename, original_filename, image_size),
        )


def migrate(
    uploads_path: str,
    bucket: str,
    region: str,
    endpoint_url: str,
    key_prefix: str,
    expected_bucket_owner: str,
    skip_existing: bool,
    dry_run: bool,
    progress_interval: int,
) -> Dict[str, int]:
    if not bucket:
        raise RuntimeError("S3 bucket is required (set --bucket or S3_BUCKET_NAME)")

    normalized_prefix = key_prefix.strip().strip("/")
    base_path = Path(uploads_path)
    client = boto3.client(
        "s3",
        region_name=region or None,
        endpoint_url=endpoint_url or None,
    )

    stats = {
        "total": 0,
        "processed": 0,
        "uploaded": 0,
        "already_present": 0,
        "missing_local": 0,
        "db_updates": 0,
        "errors": 0,
    }

    records = _file_records()
    stats["total"] = len(records)
    print(f"Found {stats['total']} image records to process.", flush=True)

    safe_interval = max(1, progress_interval)

    def report_progress(force: bool = False):
        if (
            not force
            and stats["processed"] % safe_interval != 0
            and stats["processed"] != stats["total"]
        ):
            return
        print(
            (
                f"[{stats['processed']}/{stats['total']}] "
                f"uploaded={stats['uploaded']} "
                f"already_present={stats['already_present']} "
                f"missing_local={stats['missing_local']} "
                f"db_updates={stats['db_updates']} "
                f"errors={stats['errors']}"
            ),
            flush=True,
        )

    for comparison_id, filename, original_filename in records:
        local_file = base_path / comparison_id / filename
        key = _object_key(normalized_prefix, comparison_id, filename)

        if not local_file.is_file():
            stats["missing_local"] += 1
            stats["processed"] += 1
            report_progress()
            continue

        file_size = local_file.stat().st_size
        image_size = f"{file_size} bytes"
        content_type = mimetypes.guess_type(str(local_file))[0] or "application/octet-stream"

        if skip_existing:
            try:
                if not dry_run:
                    head_kwargs = {
                        "Bucket": bucket,
                        "Key": key,
                    }
                    if expected_bucket_owner:
                        head_kwargs["ExpectedBucketOwner"] = expected_bucket_owner

                    client.head_object(
                        **head_kwargs,
                    )
                stats["already_present"] += 1
                if not dry_run:
                    _upsert_image_metadata(comparison_id, filename, original_filename, image_size)
                    stats["db_updates"] += 1
                stats["processed"] += 1
                report_progress()
                continue
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code not in {"404", "NoSuchKey", "NotFound"}:
                    stats["processed"] += 1
                    stats["errors"] += 1
                    report_progress(force=True)
                    raise

        try:
            extra_args = {
                "ContentType": content_type,
            }
            if expected_bucket_owner:
                extra_args["ExpectedBucketOwner"] = expected_bucket_owner
            if not dry_run:
                client.upload_file(
                    str(local_file),
                    bucket,
                    key,
                    ExtraArgs=extra_args,
                )
                _upsert_image_metadata(comparison_id, filename, original_filename, image_size)
                stats["db_updates"] += 1
            stats["uploaded"] += 1
        except (ClientError, BotoCoreError, OSError):
            stats["errors"] += 1
            stats["processed"] += 1
            report_progress(force=True)
            raise
        stats["processed"] += 1
        report_progress()

    report_progress(force=True)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migrate local uploads to S3 and reconcile image metadata",
    )
    parser.add_argument(
        "--uploads-path",
        default=os.getenv("UPLOADS_PATH", "uploads"),
        help="Local uploads directory (default: UPLOADS_PATH or uploads)",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("S3_BUCKET_NAME", ""),
        help="Target S3 bucket (default: S3_BUCKET_NAME env var)",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("S3_REGION", ""),
        help="S3 region (default: S3_REGION env var)",
    )
    parser.add_argument(
        "--endpoint-url",
        default=os.getenv("S3_ENDPOINT_URL", ""),
        help="S3 endpoint URL for S3-compatible providers",
    )
    parser.add_argument(
        "--key-prefix",
        default=os.getenv("S3_KEY_PREFIX", ""),
        help="Optional S3 key prefix (default: S3_KEY_PREFIX env var)",
    )
    parser.add_argument(
        "--expected-bucket-owner",
        default=os.getenv("S3_EXPECTED_BUCKET_OWNER", ""),
        help="Optional 12-digit AWS account ID expected to own the bucket",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip upload when the object already exists in S3",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without uploading or DB updates",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=25,
        help="Print progress every N processed records (default: 25)",
    )
    args = parser.parse_args()

    stats = migrate(
        uploads_path=args.uploads_path,
        bucket=args.bucket,
        region=args.region,
        endpoint_url=args.endpoint_url,
        key_prefix=args.key_prefix,
        expected_bucket_owner=args.expected_bucket_owner,
        skip_existing=args.skip_existing,
        dry_run=args.dry_run,
        progress_interval=args.progress_interval,
    )

    print("Migration completed.")
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
