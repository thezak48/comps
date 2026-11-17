import threading

import pytest

import auth
import database
import storage


def _session_cookie(user_id):
    return {"session": auth.create_access_token({"sub": str(user_id)})}


def test_public_pages_and_health(client):
    health = client.get("/health")
    home = client.get("/")
    login = client.get("/login")
    docs = client.get("/api/docs")
    schema = client.get("/openapi.json")

    assert health.json() == {"status": "healthy"}
    assert home.status_code == 200
    assert "Compare Images" in home.text
    assert login.status_code == 200
    assert docs.status_code == 200
    assert schema.status_code == 200
    assert schema.json()["info"]["title"] == "Comps API"


def test_web_login_and_logout(client, make_user):
    make_user(invitation_code="web-code")

    missing = client.post("/login", data={})
    invalid = client.post("/login", data={"username": "student", "invitation_code": "wrong"})
    success = client.post(
        "/login",
        data={"username": "student", "invitation_code": "web-code"},
        follow_redirects=False,
    )
    logout = client.get("/logout", follow_redirects=False)

    assert missing.status_code == 200
    assert "required" in missing.text
    assert invalid.status_code == 200
    assert "Invalid" in invalid.text
    assert success.status_code == 303
    assert success.cookies.get("session")
    assert logout.status_code in {302, 307}


def test_account_requires_login_and_displays_user_data(client, make_user):
    user_id = make_user()
    anonymous = client.get("/account", follow_redirects=False)
    authenticated = client.get("/account", cookies=_session_cookie(user_id))

    assert anonymous.status_code == 302
    assert anonymous.headers["location"] == "/login"
    assert authenticated.status_code == 200
    assert "API Keys" in authenticated.text


def test_admin_routes_enforce_roles(client, make_user):
    student_id = make_user()
    admin_id = make_user(username="moderator", is_admin=True)
    super_id = make_user(username="super", is_admin=True, is_super_admin=True)

    assert client.get("/admin", follow_redirects=False).status_code in {302, 307}
    student_admin_page = client.get(
        "/admin", cookies=_session_cookie(student_id), follow_redirects=False
    )
    assert student_admin_page.status_code in {302, 307}
    assert client.get("/admin", cookies=_session_cookie(admin_id)).status_code == 200
    forbidden_create = client.post("/admin/create-invitation", cookies=_session_cookie(student_id))
    assert forbidden_create.status_code == 403
    assert (
        client.post(
            "/admin/create-invitation",
            cookies=_session_cookie(admin_id),
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/admin/user/set-admin",
            cookies=_session_cookie(super_id),
            json={"user_id": student_id, "is_admin": True},
            follow_redirects=False,
        ).status_code
        == 303
    )


def test_api_key_account_endpoints(client, make_user):
    user_id = make_user()
    cookies = _session_cookie(user_id)

    assert client.post("/account/api-keys/create", data={"key_name": "test"}).status_code == 401
    empty = client.post("/account/api-keys/create", data={"key_name": " "}, cookies=cookies)
    created = client.post("/account/api-keys/create", data={"key_name": "browser"}, cookies=cookies)
    key_id = auth.get_user_api_keys(user_id)[0]["id"]
    deleted = client.delete(f"/account/api-keys/delete/{key_id}", cookies=cookies)

    assert empty.status_code == 400
    assert created.status_code == 201
    assert created.json()["key"].startswith("comps_")
    assert deleted.status_code == 200


def test_compare_page_renders_images_and_missing_returns_404(client):
    comparison_id = "88888888-8888-8888-8888-888888888888"
    database.create_comparison(
        comparison_id,
        "Comparison",
        "Shown",
        [],
        {"total_rows": 25, "total_columns": 2, "expiration_days": 7},
    )
    database.store_image_position(comparison_id, "image.png", 0, 0)
    database.store_image_metadata(comparison_id, "image.png", "original.png", "5 bytes")

    response = client.get(f"/compare/{comparison_id}")
    missing = client.get("/compare/99999999-9999-9999-9999-999999999999")

    assert response.status_code == 200
    assert "Comparison" in response.text
    assert "original.png" in response.text
    assert response.context["images"] == [f"/uploads/{comparison_id}/image.png"]
    assert missing.status_code == 404


def test_s3_image_redirect_uses_threadpool_and_does_not_cache_redirect(client, monkeypatch):
    import main

    thread_ids = {}
    original_threadpool = main.run_in_threadpool

    async def track_threadpool(function, *args):
        thread_ids["route"] = threading.get_ident()
        return await original_threadpool(function, *args)

    def sign_url(comparison_id, filename):
        thread_ids["signer"] = threading.get_ident()
        return "https://s3.example.test/image?signature=test"

    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(main, "run_in_threadpool", track_threadpool)
    monkeypatch.setattr(main, "get_presigned_image_url", sign_url)

    response = client.get(
        "/uploads/88888888-8888-8888-8888-888888888888/image.png", follow_redirects=False
    )
    assert response.status_code == 307
    assert response.headers["location"] == "https://s3.example.test/image?signature=test"
    assert response.headers["cache-control"] == "no-store"
    assert thread_ids["route"] != thread_ids["signer"]


def test_public_s3_image_redirect_skips_signer(client, monkeypatch):
    import main

    def unexpected_sign(*args):
        pytest.fail("Public image URLs must not invoke the S3 signer")

    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_PUBLIC_BASE_URL", "https://images.example.test")
    monkeypatch.setattr(storage, "S3_KEY_PREFIX", "public images")
    monkeypatch.setattr(main, "get_presigned_image_url", unexpected_sign)
    comparison_id = "88888888-8888-8888-8888-888888888888"

    response = client.get(f"/uploads/{comparison_id}/image.png", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == (
        f"https://images.example.test/public%20images/{comparison_id}/image.png"
    )
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("error,expected_status", [(FileNotFoundError(), 404), (OSError(), 502)])
def test_s3_image_redirect_translates_storage_errors(client, monkeypatch, error, expected_status):
    import main

    def failing_sign(*args):
        raise error

    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(main, "get_presigned_image_url", failing_sign)
    response = client.get(
        "/uploads/88888888-8888-8888-8888-888888888888/image.png", follow_redirects=False
    )
    assert response.status_code == expected_status


def test_public_s3_comparison_page_embeds_public_urls(client, monkeypatch):
    comparison_id = "88888888-8888-8888-8888-888888888888"
    database.create_comparison(
        comparison_id, "Public", None, [], {"total_rows": 1, "total_columns": 2}
    )
    database.store_image_position(comparison_id, "image.png", 0, 0)
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "S3_PUBLIC_BASE_URL", "https://images.example.test")
    monkeypatch.setattr(storage, "S3_KEY_PREFIX", "public")

    response = client.get(f"/compare/{comparison_id}")
    expected_url = f"https://images.example.test/public/{comparison_id}/image.png"
    assert response.status_code == 200
    assert response.context["images"] == [expected_url]
    assert f'src="{expected_url}"' in response.text
