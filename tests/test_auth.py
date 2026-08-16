import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import auth
from db import execute, query_one


def _request(headers=None, cookies=None):
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    if cookies:
        raw_headers.append(
            (
                "cookie".encode(),
                "; ".join(f"{key}={value}" for key, value in cookies.items()).encode(),
            )
        )
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw_headers})


def test_invitation_registration_and_authentication(isolated_db):
    admin_id = query_one("SELECT id FROM users WHERE username = 'admin'")[0]
    code = auth.create_invitation_code(admin_id)

    assert auth.verify_invitation_code(code) is True
    user = auth.register_user("new-user", code)
    assert user["username"] == "new-user"
    assert auth.verify_invitation_code(code) is False
    assert auth.authenticate_user("new-user", code)["id"] == user["id"]
    assert auth.register_user("another-user", code) is None


def test_tokens_resolve_users_and_reject_invalid_tokens(isolated_db, make_user):
    user_id = make_user()
    token = auth.create_access_token({"sub": str(user_id)})

    user = asyncio.run(auth.get_current_user_from_token(f"Bearer {token}"))

    assert user["id"] == user_id
    assert asyncio.run(auth.get_current_user_from_token("invalid")) is None


def test_api_key_lifecycle_and_optional_user(isolated_db, make_user):
    user_id = make_user()
    key = auth.create_api_key(user_id, "automation")

    assert key.startswith("comps_")
    assert auth.get_user_from_api_key(key)["id"] == user_id
    request_user = asyncio.run(auth.get_optional_user(_request(headers={"Authorization": key})))
    assert request_user["id"] == user_id
    keys = auth.get_user_api_keys(user_id)
    assert keys[0]["key_name"] == "automation"
    assert keys[0]["last_used_at"] is not None
    assert auth.delete_api_key(user_id, keys[0]["id"]) is True
    assert auth.get_user_from_api_key(key) is None


def test_optional_user_falls_back_to_session_cookie(isolated_db, make_user):
    user_id = make_user()
    token = auth.create_access_token({"sub": str(user_id)})

    user = asyncio.run(auth.get_optional_user(_request(cookies={"session": token})))

    assert user["id"] == user_id


def test_role_and_write_access_helpers():
    assert auth.is_admin({"is_admin": True}) is True
    assert auth.is_super_admin({"is_super_admin": True}) is True
    assert auth.comparison_never_expires({"never_expire_comparisons": True}) is True
    with pytest.raises(HTTPException, match="permission") as raised:
        auth.require_comparison_write_access({"user_id": 1}, {"id": 2})
    assert raised.value.status_code == 403


def test_admin_queries_and_updates(isolated_db, make_user):
    user_id = make_user()
    auth.set_admin_status(user_id, True)
    execute(
        "INSERT INTO invitation_codes (code, created_by) VALUES (?, ?)",
        ("visible-code", user_id),
    )

    assert query_one("SELECT is_admin FROM users WHERE id = ?", (user_id,))[0] == 1
    assert auth.get_user_invitation_codes(user_id)[0]["code"] == "visible-code"
    assert any(user["id"] == user_id for user in auth.get_all_users())
