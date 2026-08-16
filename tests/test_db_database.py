from datetime import datetime, timedelta
from unittest.mock import Mock

import database
import db
from migrations.manager import MigrationManager


def test_migrations_create_complete_schema(isolated_db):
    tables = {row[0] for row in db.query("SELECT name FROM sqlite_master WHERE type = 'table'")}

    assert {
        "api_keys",
        "comparisons",
        "image_metadata",
        "image_positions",
        "invitation_codes",
        "migrations",
        "tags",
        "users",
    } <= tables
    assert MigrationManager().get_current_version() == "010"


def test_db_helpers_execute_and_query(isolated_db):
    db.execute("CREATE TABLE helper_test (id INTEGER, name TEXT)")
    db.executemany(
        "INSERT INTO helper_test (id, name) VALUES (?, ?)",
        [(1, "one"), (2, "two")],
    )

    assert db.backend_name() == "sqlite"
    assert db.query_one("SELECT name FROM helper_test WHERE id = ?", (1,)) == ("one",)
    assert db.query_dicts("SELECT id, name FROM helper_test ORDER BY id") == [
        {"id": 1, "name": "one"},
        {"id": 2, "name": "two"},
    ]
    assert db.execute_with_rowcount("DELETE FROM helper_test WHERE id = ?", (2,)) == 1


def test_comparison_and_image_lifecycle(isolated_db, make_user):
    user_id = make_user(never_expire=True)
    database.create_comparison(
        "11111111-1111-1111-1111-111111111111",
        "Internal",
        "Visible",
        ["one", "two"],
        {
            "total_rows": 2,
            "total_columns": 3,
            "expiration_type": "from_creation",
            "expiration_days": 30,
            "never_expire": True,
        },
        user_id=user_id,
    )
    database.store_image_position("11111111-1111-1111-1111-111111111111", "image.png", 1, 2)
    database.store_image_metadata(
        "11111111-1111-1111-1111-111111111111",
        "image.png",
        "original.png",
        "12 bytes",
    )
    database.update_image_custom_name("11111111-1111-1111-1111-111111111111", "image.png", "Custom")

    comparison = database.get_comparison("11111111-1111-1111-1111-111111111111")
    image = db.query_one(
        """
        SELECT original_filename, image_size, custom_name
        FROM image_metadata WHERE comparison_id = ?
        """,
        (comparison["id"],),
    )

    assert comparison["tags"] == ["one", "two"]
    assert comparison["user_id"] == user_id
    assert comparison["never_expire"] is True
    assert comparison["expiration_days"] == 30
    assert image == ("original.png", "12 bytes", "Custom")
    assert database.get_user_comparisons(user_id)[0]["id"] == comparison["id"]


def test_expiration_respects_mode_and_never_expire(isolated_db):
    old = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    recent = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for comparison_id, mode, never_expire in [
        ("expired-creation", "from_creation", False),
        ("expired-access", "from_last_access", False),
        ("kept", "from_creation", True),
    ]:
        database.create_comparison(
            comparison_id,
            comparison_id,
            None,
            [],
            {
                "expiration_type": mode,
                "expiration_days": 7,
                "never_expire": never_expire,
            },
        )
        db.execute(
            "UPDATE comparisons SET created_at = ?, last_accessed = ? WHERE id = ?",
            (old, old if mode == "from_last_access" else recent, comparison_id),
        )

    assert set(database.get_expired_comparisons(7)) == {
        "expired-creation",
        "expired-access",
    }


def test_delete_comparison_removes_rows_and_assets(isolated_db, monkeypatch):
    comparison_id = "22222222-2222-2222-2222-222222222222"
    database.create_comparison(comparison_id, "Delete", None, ["tag"], {}, None)
    database.store_image_position(comparison_id, "image.png", 0, 0)
    database.store_image_metadata(comparison_id, "image.png", "image.png", "1 byte")
    delete_assets = Mock()
    monkeypatch.setattr(database, "delete_comparison_assets", delete_assets)

    database.delete_comparison(comparison_id)

    assert database.get_comparison(comparison_id) is None
    tag_count = db.query_one("SELECT COUNT(*) FROM tags WHERE comparison_id = ?", (comparison_id,))[
        0
    ]
    assert tag_count == 0
    delete_assets.assert_called_once_with(comparison_id, None, filenames=["image.png"])
