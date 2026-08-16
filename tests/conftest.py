import hashlib
import os
import tempfile
from pathlib import Path

import pytest

_BOOTSTRAP_ROOT = Path(tempfile.mkdtemp(prefix="comps-tests-"))
os.environ["DB_BACKEND"] = "sqlite"
os.environ["DB_PATH"] = str(_BOOTSTRAP_ROOT / "bootstrap.db")
os.environ["UPLOADS_PATH"] = str(_BOOTSTRAP_ROOT / "uploads")
os.environ["STORAGE_BACKEND"] = "local"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_INVITATION_CODE"] = "test-admin-code"

import database  # noqa: E402
import storage  # noqa: E402
from db import execute, query_one  # noqa: E402


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "comparisons.db"
    uploads_path = tmp_path / "uploads"
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("UPLOADS_PATH", str(uploads_path))
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "UPLOADS_PATH", str(uploads_path))
    database.init_db()
    return db_path


@pytest.fixture
def make_user(isolated_db):
    def factory(
        username="student",
        invitation_code="student-code",
        *,
        is_admin=False,
        is_super_admin=False,
        never_expire=False,
    ):
        execute(
            """
            INSERT INTO users (
                username, invitation_code_hash, is_admin,
                never_expire_comparisons, is_super_admin
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                hashlib.sha256(invitation_code.encode()).hexdigest(),
                is_admin,
                never_expire,
                is_super_admin,
            ),
        )
        return query_one(
            "SELECT id, username FROM users WHERE username = ?",
            (username,),
        )[0]

    return factory


@pytest.fixture
def client(isolated_db):
    from fastapi.testclient import TestClient

    import main

    test_client = TestClient(main.app)
    yield test_client
    test_client.close()


@pytest.fixture
def api_credentials(make_user):
    import auth

    user_id = make_user()
    api_key = auth.create_api_key(user_id, "tests")
    return user_id, {"Authorization": api_key}
