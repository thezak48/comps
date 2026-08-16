from io import BytesIO

from PIL import Image

import auth
import database
from db import execute, query_one


def png_bytes():
    """A real PNG, so these cases keep working once uploads are content-checked."""
    buffer = BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_api_login_accepts_valid_credentials(client, make_user):
    user_id = make_user(invitation_code="login-code")

    response = client.post(
        "/api/v1/login",
        data={"username": "student", "password": "login-code"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert user_id


def test_api_login_rejects_invalid_credentials(client, make_user):
    make_user(invitation_code="correct-code")

    response = client.post(
        "/api/v1/login",
        data={"username": "student", "password": "wrong-code"},
    )

    assert response.status_code == 401


def test_json_comparison_create_list_and_detail(client, api_credentials):
    user_id, headers = api_credentials

    created = client.post(
        "/api/v1/comparisons",
        headers=headers,
        json={
            "name": "API comparison",
            "show_name": "Shown",
            "tags": ["api", "test"],
            "total_rows": 2,
            "total_columns": 3,
            "expiration_type": "from_creation",
            "expiration_days": 30,
        },
    )

    assert created.status_code == 201
    comparison_id = created.json()["id"]
    assert query_one("SELECT user_id FROM comparisons WHERE id = ?", (comparison_id,))[0] == user_id
    assert created.json()["expiration_days"] == 30

    listed = client.get("/api/v1/comparisons", headers=headers)
    detailed = client.get(f"/api/v1/comparisons/{comparison_id}")
    assert listed.status_code == 200
    assert listed.json()[0]["tags"] == ["api", "test"]
    assert detailed.status_code == 200
    assert detailed.json()["images"] == []


def test_comparison_listing_requires_authentication(client):
    assert client.get("/api/v1/comparisons").status_code == 401


def test_comparison_listing_is_scoped_to_the_caller(client, api_credentials, make_user):
    _, owner_headers = api_credentials
    admin_id = make_user(username="boss", invitation_code="boss-code", is_admin=True)
    admin_headers = {"Authorization": auth.create_api_key(admin_id, "admin")}

    client.post("/api/v1/comparisons", headers=owner_headers, json={"name": "Mine"})
    client.post("/api/v1/comparisons", headers=admin_headers, json={"name": "Theirs"})

    owned = client.get("/api/v1/comparisons", headers=owner_headers)
    everything = client.get("/api/v1/comparisons", headers=admin_headers)

    assert [row["name"] for row in owned.json()] == ["Mine"]
    assert {row["name"] for row in everything.json()} == {"Mine", "Theirs"}


def test_ownerless_comparison_write_requires_the_edit_token(client):
    created = client.post("/api/v1/comparison", data={"name": "Anon"}).json()
    comparison_id = created["comparison_id"]
    form = {"row": "0", "column": "0", "original_filename": "shot.png"}
    upload = {"file": ("shot.png", png_bytes(), "image/png")}

    without = client.post(f"/api/v1/comparison/{comparison_id}/image", data=form, files=upload)
    wrong = client.post(
        f"/api/v1/comparison/{comparison_id}/image",
        headers={"X-Edit-Token": "not-the-token"},
        data=form,
        files=upload,
    )
    correct = client.post(
        f"/api/v1/comparison/{comparison_id}/image",
        headers={"X-Edit-Token": created["edit_token"]},
        data=form,
        files=upload,
    )

    assert without.status_code == 403
    assert wrong.status_code == 403
    assert correct.status_code == 200


def test_edit_token_stops_working_once_expired(client):
    created = client.post("/api/v1/comparison", data={"name": "Anon"}).json()
    execute(
        "UPDATE comparisons SET edit_token_expires_at = ? WHERE id = ?",
        (1, created["comparison_id"]),
    )

    response = client.post(
        f"/api/v1/comparison/{created['comparison_id']}/image",
        headers={"X-Edit-Token": created["edit_token"]},
        data={"row": "0", "column": "0", "original_filename": "shot.png"},
        files={"file": ("shot.png", png_bytes(), "image/png")},
    )

    assert response.status_code == 403


def test_owned_comparison_needs_no_edit_token(client, api_credentials):
    _, headers = api_credentials
    created = client.post("/api/v1/comparison", headers=headers, data={"name": "Owned"}).json()

    assert "edit_token" not in created

    response = client.post(
        f"/api/v1/comparison/{created['comparison_id']}/image",
        headers=headers,
        data={"row": "0", "column": "0", "original_filename": "shot.png"},
        files={"file": ("shot.png", png_bytes(), "image/png")},
    )

    assert response.status_code == 200


def test_json_comparison_rejects_invalid_expiration(client):
    response = client.post(
        "/api/v1/comparisons",
        json={"expiration_type": "never", "expiration_days": 365},
    )

    assert response.status_code == 422


def test_form_comparison_validates_expiration_and_entitlement(client, make_user):
    user_id = make_user(never_expire=False)
    key = auth.create_api_key(user_id, "form")
    headers = {"Authorization": key}

    invalid = client.post(
        "/api/v1/comparison",
        headers=headers,
        data={"expiration_type": "from_creation", "expiration_days": "365"},
    )
    valid = client.post(
        "/api/v1/comparison",
        headers=headers,
        data={
            "name": "Form comparison",
            "expiration_type": "from_creation",
            "expiration_days": "7",
            "expiration_enabled": "false",
        },
    )

    assert invalid.status_code == 422
    assert valid.status_code == 200
    comparison_id = valid.json()["comparison_id"]
    row = query_one(
        "SELECT expiration_type, expiration_days, never_expire FROM comparisons WHERE id = ?",
        (comparison_id,),
    )
    assert row == ("from_creation", 7, 0)


def test_owned_image_upload_update_and_delete(client, api_credentials, make_user):
    owner_id, owner_headers = api_credentials
    other_id = make_user(username="other", invitation_code="other-code")
    other_headers = {"Authorization": auth.create_api_key(other_id, "other")}
    comparison_id = "44444444-4444-4444-4444-444444444444"
    database.create_comparison(
        comparison_id,
        "Owned",
        None,
        [],
        {"total_rows": 1, "total_columns": 2},
        user_id=owner_id,
    )
    upload = {
        "file": ("image.png", b"image bytes", "image/png"),
    }
    form = {"row": "0", "column": "0", "original_filename": "image.png"}

    forbidden = client.post(
        f"/api/v1/comparison/{comparison_id}/image",
        headers=other_headers,
        data=form,
        files=upload,
    )
    uploaded = client.post(
        f"/api/v1/comparison/{comparison_id}/image",
        headers=owner_headers,
        data=form,
        files=upload,
    )

    assert forbidden.status_code == 403
    assert uploaded.status_code == 200
    filename = uploaded.json()["filename"]

    forbidden_update = client.put(
        f"/api/v1/comparisons/{comparison_id}/images/{filename}",
        headers=other_headers,
        json={"custom_name": "Wrong"},
    )
    updated = client.put(
        f"/api/v1/comparisons/{comparison_id}/images/{filename}",
        headers=owner_headers,
        json={"custom_name": "Correct"},
    )
    assert forbidden_update.status_code == 403
    assert updated.status_code == 200
    assert query_one(
        "SELECT custom_name FROM image_metadata WHERE comparison_id = ? AND filename = ?",
        (comparison_id, filename),
    ) == ("Correct",)

    forbidden_delete = client.delete(
        f"/api/v1/delete-comparison/{comparison_id}", headers=other_headers
    )
    deleted = client.delete(f"/api/v1/delete-comparison/{comparison_id}", headers=owner_headers)
    assert forbidden_delete.status_code == 403
    assert deleted.status_code == 200
    assert database.get_comparison(comparison_id) is None


def test_missing_comparison_routes_return_not_found(client):
    missing_id = "55555555-5555-5555-5555-555555555555"

    assert client.get(f"/api/v1/comparisons/{missing_id}").status_code == 404
    response = client.post(
        f"/api/v1/comparison/{missing_id}/image",
        data={"row": "0", "column": "0", "original_filename": "image.png"},
        files={"file": ("image.png", b"image", "image/png")},
    )
    assert response.status_code == 404
