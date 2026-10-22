import asyncio
import threading
from io import BytesIO
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError
from fastapi import UploadFile

import storage

COMPARISON_ID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def signing_client(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.head_calls = []
            self.sign_calls = []

        def head_object(self, **kwargs):
            self.head_calls.append(kwargs)
            return {"ContentLength": 10}

        def generate_presigned_url(self, operation, **kwargs):
            self.sign_calls.append((operation, kwargs))
            return f"https://images.example.test/image?signature={len(self.sign_calls)}"

    client = FakeClient()
    clock = [100.0]
    monkeypatch.setattr(storage, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_BUCKET_NAME", "bucket")
    monkeypatch.setattr(storage, "S3_KEY_PREFIX", "prefix")
    monkeypatch.setattr(storage, "S3_PRESIGNED_URL_TTL_SECONDS", 60)
    monkeypatch.setattr(storage, "_get_s3_client", lambda: client)
    return client, clock


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


def test_presigned_url_cache_reuses_url_and_avoids_s3_requests(signing_client):
    client, _ = signing_client
    first = storage.get_presigned_image_url(COMPARISON_ID, "image.png")

    assert storage.get_presigned_image_url(COMPARISON_ID, "image.png") == first
    assert len(client.head_calls) == len(client.sign_calls) == 1


def test_presigned_url_cache_refreshes_before_expiry(signing_client):
    client, clock = signing_client
    first = storage.get_presigned_image_url(COMPARISON_ID, "image.png")
    clock[0] += 54
    assert storage.get_presigned_image_url(COMPARISON_ID, "image.png") == first

    clock[0] += 1
    assert storage.get_presigned_image_url(COMPARISON_ID, "image.png") != first
    assert len(client.sign_calls) == 2


@pytest.mark.parametrize("ttl,expected", [(0, 1), (5, 5), (999999, 604800)])
def test_presigned_url_ttl_is_bounded(signing_client, monkeypatch, ttl, expected):
    client, _ = signing_client
    monkeypatch.setattr(storage, "S3_PRESIGNED_URL_TTL_SECONDS", ttl)
    storage.get_presigned_image_url(COMPARISON_ID, "image.png")

    assert client.sign_calls[0][1]["ExpiresIn"] == expected
    if ttl <= 5:
        assert not storage._presigned_url_cache


def test_presigned_url_cache_can_be_disabled(signing_client, monkeypatch):
    client, _ = signing_client
    monkeypatch.setattr(storage, "S3_PRESIGNED_URL_CACHE_MAX_SIZE", 0)
    first = storage.get_presigned_image_url(COMPARISON_ID, "image.png")

    assert storage.get_presigned_image_url(COMPARISON_ID, "image.png") != first
    assert not storage._presigned_url_cache
    assert len(client.sign_calls) == 2


def test_presigned_url_cache_is_bounded_and_prunes_expired_entries(signing_client, monkeypatch):
    _, clock = signing_client
    monkeypatch.setattr(storage, "S3_PRESIGNED_URL_CACHE_MAX_SIZE", 2)
    for filename in ["first.png", "second.png", "third.png"]:
        storage.get_presigned_image_url(COMPARISON_ID, filename)

    assert list(storage._presigned_url_cache) == [
        f"prefix/{COMPARISON_ID}/second.png",
        f"prefix/{COMPARISON_ID}/third.png",
    ]
    clock[0] += 60
    storage.get_presigned_image_url(COMPARISON_ID, "fresh.png")
    assert list(storage._presigned_url_cache) == [f"prefix/{COMPARISON_ID}/fresh.png"]


def test_presigned_url_cache_does_not_extend_signing_lifetime(signing_client, monkeypatch):
    client, clock = signing_client
    original_sign = client.generate_presigned_url

    def slow_sign(*args, **kwargs):
        clock[0] += 58
        return original_sign(*args, **kwargs)

    monkeypatch.setattr(client, "generate_presigned_url", slow_sign)
    storage.get_presigned_image_url(COMPARISON_ID, "image.png")
    assert not storage._presigned_url_cache


def test_inflight_lookup_cannot_repopulate_invalidated_cache(signing_client, monkeypatch):
    client, _ = signing_client
    original_sign = client.generate_presigned_url

    def sign_during_invalidation(*args, **kwargs):
        storage._evict_presigned_url_cache(prefix=f"prefix/{COMPARISON_ID}/")
        return original_sign(*args, **kwargs)

    monkeypatch.setattr(client, "generate_presigned_url", sign_during_invalidation)
    storage.get_presigned_image_url(COMPARISON_ID, "image.png")
    assert not storage._presigned_url_cache


@pytest.mark.parametrize("fails", [False, True])
def test_upload_invalidates_urls_before_and_after_write(signing_client, monkeypatch, fails):
    client, _ = signing_client
    key = f"prefix/{COMPARISON_ID}/image.png"
    storage.get_presigned_image_url(COMPARISON_ID, "image.png")

    def upload(*args):
        assert key not in storage._presigned_url_cache
        storage.get_presigned_image_url(COMPARISON_ID, "image.png")
        assert key in storage._presigned_url_cache
        if fails:
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")

    monkeypatch.setattr(client, "upload_fileobj", upload, raising=False)
    upload_file = UploadFile(filename="image.png", file=BytesIO(b"image-data"))
    if fails:
        with pytest.raises(OSError, match="Failed to upload"):
            asyncio.run(storage.save_upload_file(COMPARISON_ID, "image.png", upload_file))
    else:
        assert asyncio.run(storage.save_upload_file(COMPARISON_ID, "image.png", upload_file)) == 10
    assert key not in storage._presigned_url_cache


def test_s3_upload_and_metadata_lookup_run_off_event_loop(signing_client, monkeypatch):
    client, _ = signing_client
    worker_threads = []

    def upload(*args):
        worker_threads.append(threading.get_ident())

    def head(**kwargs):
        worker_threads.append(threading.get_ident())
        return {"ContentLength": 10}

    monkeypatch.setattr(client, "upload_fileobj", upload, raising=False)
    monkeypatch.setattr(client, "head_object", head)
    upload_file = UploadFile(filename="image.png", file=BytesIO(b"image-data"))
    event_loop_thread = threading.get_ident()
    asyncio.run(storage.save_upload_file(COMPARISON_ID, "image.png", upload_file))

    assert len(worker_threads) == 2
    assert all(thread != event_loop_thread for thread in worker_threads)


@pytest.mark.parametrize("filenames", [["image.png"], None])
@pytest.mark.parametrize("fails", [False, True])
def test_delete_invalidates_urls_and_preserves_other_comparisons(
    signing_client, monkeypatch, filenames, fails
):
    client, _ = signing_client
    other_id = "44444444-4444-4444-4444-444444444444"
    key = f"prefix/{COMPARISON_ID}/image.png"
    other_key = f"prefix/{other_id}/image.png"
    storage.get_presigned_image_url(COMPARISON_ID, "image.png")
    storage.get_presigned_image_url(other_id, "image.png")

    def delete(**kwargs):
        assert key not in storage._presigned_url_cache
        storage.get_presigned_image_url(COMPARISON_ID, "image.png")
        if fails:
            return {"Errors": [{"Key": key, "Code": "AccessDenied"}]}
        return {}

    monkeypatch.setattr(client, "delete_objects", delete, raising=False)
    monkeypatch.setattr(
        client, "list_objects_v2", lambda **kwargs: {"Contents": [{"Key": key}]}, raising=False
    )
    if fails:
        with pytest.raises(OSError, match="S3 reported delete errors"):
            storage.delete_comparison_assets(COMPARISON_ID, filenames=filenames)
    else:
        storage.delete_comparison_assets(COMPARISON_ID, filenames=filenames)
    assert key not in storage._presigned_url_cache
    assert other_key in storage._presigned_url_cache


@pytest.mark.parametrize("backend", ["local", "s3"])
def test_browser_image_url_falls_back_to_app_without_public_s3(monkeypatch, backend):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", backend)
    monkeypatch.setattr(storage, "S3_KEY_PREFIX", "ignored-for-app-paths")
    if backend == "local":
        monkeypatch.setattr(storage, "S3_PUBLIC_BASE_URL", "https://images.example.test")

    assert storage.get_browser_image_url(COMPARISON_ID, "picture #1?.png") == (
        f"/uploads/{COMPARISON_ID}/picture%20%231%3F.png"
    )


def test_public_browser_url_encodes_object_key_and_preserves_base_path(monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_PUBLIC_BASE_URL", "https://images.example.test/assets/")
    monkeypatch.setattr(storage, "S3_KEY_PREFIX", "team images/#cache")

    assert storage.get_browser_image_url(COMPARISON_ID, "picture #1?.png") == (
        f"https://images.example.test/assets/team%20images/%23cache/"
        f"{COMPARISON_ID}/picture%20%231%3F.png"
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "javascript:alert(1)",
        "//images.example.test",
        "/images",
        "https://",
        "https://user:secret@images.example.test",
        "https://@images.example.test",
        "https://images.example.test?token=secret",
        "https://images.example.test?",
        "https://images.example.test#images",
        "https://images.example.test#",
        "https://images.example.test:invalid",
        "https://images.example.test:99999",
        "https://images.example.test\\other",
        "https://images.example.test/with space",
        "https://images.example.test/\x00",
    ],
)
def test_public_browser_url_rejects_invalid_bases(monkeypatch, base_url):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_PUBLIC_BASE_URL", base_url)
    with pytest.raises(OSError, match="S3_PUBLIC_BASE_URL"):
        storage.get_browser_image_url(COMPARISON_ID, "image.png")


def test_storage_readiness_rejects_invalid_public_url_before_s3_calls(monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_BUCKET_NAME", "bucket")
    monkeypatch.setattr(storage, "S3_PUBLIC_BASE_URL", "invalid")
    with pytest.raises(RuntimeError, match="S3_PUBLIC_BASE_URL"):
        storage.ensure_storage_ready()
