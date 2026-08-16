import auth
import database


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
    assert missing.status_code == 404
