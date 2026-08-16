import asyncio
from io import BytesIO

import pytest
from botocore.exceptions import ClientError
from fastapi import UploadFile

import storage

COMPARISON_ID = "33333333-3333-3333-3333-333333333333"


def test_local_storage_create_save_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "UPLOADS_PATH", str(tmp_path))
    upload = UploadFile(filename="picture.png", file=BytesIO(b"image-data"))

    storage.ensure_storage_ready()
    storage.create_comparison_storage(COMPARISON_ID)
    size = asyncio.run(storage.save_upload_file(COMPARISON_ID, "picture.png", upload))

    image_path = tmp_path / COMPARISON_ID / "picture.png"
    assert size == 10
    assert image_path.read_bytes() == b"image-data"
    storage.delete_comparison_assets(COMPARISON_ID)
    assert not image_path.parent.exists()


@pytest.mark.parametrize(
    "comparison_id,filename",
    [
        ("not-a-uuid", "image.png"),
        (COMPARISON_ID, "../image.png"),
        (COMPARISON_ID, "folder/image.png"),
        (COMPARISON_ID, ""),
    ],
)
def test_storage_rejects_unsafe_paths(comparison_id, filename):
    with pytest.raises(OSError):
        storage._normalize_comparison_id(comparison_id)
        storage._normalize_filename(filename)


def test_s3_object_keys_honor_prefix(monkeypatch):
    monkeypatch.setattr(storage, "S3_KEY_PREFIX", "testing")

    assert storage._get_object_key(COMPARISON_ID, "image.png") == (
        f"testing/{COMPARISON_ID}/image.png"
    )
    assert storage._get_object_key_prefix(COMPARISON_ID) == f"testing/{COMPARISON_ID}/"


def test_s3_delete_is_batched(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = []

        def delete_objects(self, **kwargs):
            self.calls.append(kwargs)
            return {}

    client = FakeClient()
    monkeypatch.setattr(storage, "S3_BUCKET_NAME", "bucket")
    storage._delete_s3_keys(client, [f"key-{index}" for index in range(1001)])

    assert len(client.calls) == 2
    assert len(client.calls[0]["Delete"]["Objects"]) == 1000
    assert len(client.calls[1]["Delete"]["Objects"]) == 1


def test_s3_storage_readiness_requires_bucket(monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_BUCKET_NAME", "")

    with pytest.raises(RuntimeError, match="S3_BUCKET_NAME"):
        storage.ensure_storage_ready()


def test_s3_save_and_presigned_url(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.uploaded = b""

        def head_bucket(self, **kwargs):
            assert kwargs == {"Bucket": "bucket"}

        def upload_fileobj(self, fileobj, bucket, key, extra):
            assert bucket == "bucket"
            assert key == f"prefix/{COMPARISON_ID}/picture.png"
            assert extra == {"ContentType": "image/png"}
            self.uploaded = fileobj.read()

        def head_object(self, **kwargs):
            return {"ContentLength": len(self.uploaded)}

        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert operation == "get_object"
            assert Params["Bucket"] == "bucket"
            assert ExpiresIn == 60
            return "https://example.test/image"

    client = FakeClient()
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_BUCKET_NAME", "bucket")
    monkeypatch.setattr(storage, "S3_KEY_PREFIX", "prefix")
    monkeypatch.setattr(storage, "S3_PRESIGNED_URL_TTL_SECONDS", 60)
    monkeypatch.setattr(storage, "_get_s3_client", lambda: client)
    upload = UploadFile(
        filename="picture.png",
        file=BytesIO(b"image-data"),
        headers={"content-type": "image/png"},
    )

    storage.ensure_storage_ready()
    size = asyncio.run(storage.save_upload_file(COMPARISON_ID, "picture.png", upload))
    url = storage.get_presigned_image_url(COMPARISON_ID, "picture.png")

    assert size == 10
    assert client.uploaded == b"image-data"
    assert url == "https://example.test/image"


def test_s3_presigned_url_translates_not_found(monkeypatch):
    class MissingClient:
        def head_object(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "404", "Message": "missing"}},
                "HeadObject",
            )

    monkeypatch.setattr(storage, "S3_BUCKET_NAME", "bucket")
    monkeypatch.setattr(storage, "_get_s3_client", lambda: MissingClient())

    with pytest.raises(FileNotFoundError):
        storage.get_presigned_image_url(COMPARISON_ID, "missing.png")


def test_s3_delete_can_list_paginated_objects(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.list_calls = []
            self.deleted = []

        def list_objects_v2(self, **kwargs):
            self.list_calls.append(kwargs)
            if len(self.list_calls) == 1:
                return {
                    "Contents": [{"Key": "first"}],
                    "IsTruncated": True,
                    "NextContinuationToken": "next",
                }
            return {"Contents": [{"Key": "second"}], "IsTruncated": False}

        def delete_objects(self, **kwargs):
            self.deleted.extend(item["Key"] for item in kwargs["Delete"]["Objects"])
            return {}

    client = FakeClient()
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_BUCKET_NAME", "bucket")
    monkeypatch.setattr(storage, "S3_KEY_PREFIX", "")
    monkeypatch.setattr(storage, "_get_s3_client", lambda: client)

    storage.delete_comparison_assets(COMPARISON_ID)

    assert client.list_calls[1]["ContinuationToken"] == "next"
    assert client.deleted == ["first", "second"]
