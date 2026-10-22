import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

import auth
import database

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.mark.parametrize(
    "template_name",
    sorted(
        str(path.relative_to(TEMPLATES))
        for path in TEMPLATES.rglob("*")
        if path.is_file() and path.suffix in {".jinja", ".html"}
    ),
)
def test_all_html_and_jinja_templates_compile(client, template_name):
    import main

    assert main.templates.env.get_template(template_name).name == template_name


def test_swagger_stylesheet_and_initializer_survive_formatting(client):
    response = client.get("/api/docs")
    assert response.status_code == 200
    elements = Elements(response.text).elements
    assert any(
        tag == "link"
        and attrs.get("rel") == "stylesheet"
        and attrs.get("href") == "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
        for tag, attrs in elements
    )
    assert any(
        tag == "script"
        and attrs.get("src")
        == "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
        for tag, attrs in elements
    )
    assert "SwaggerUIBundle({" in response.text
    assert "url: '/openapi.json'" in response.text


@pytest.mark.parametrize(
    "target_role,expected_checked", [("ordinary", False), ("moderator", True), ("root", None)]
)
def test_admin_switches_keep_their_role_dependent_attributes(
    client, make_user, target_role, expected_checked
):
    root_id = make_user(username="root", is_admin=True, is_super_admin=True)
    user_ids = {
        "ordinary": make_user(username="ordinary"),
        "moderator": make_user(username="moderator", is_admin=True),
        "root": root_id,
    }
    client.cookies.set("session", auth.create_access_token({"sub": str(root_id)}))
    response = client.get("/admin")
    assert response.status_code == 200
    switches = {
        attrs["id"]: attrs
        for tag, attrs in Elements(response.text).elements
        if tag == "input" and attrs.get("id", "").startswith("adminSwitch")
    }
    switch_id = f"adminSwitch{user_ids[target_role]}"
    if expected_checked is None:
        assert switch_id not in switches
    else:
        assert ("checked" in switches[switch_id]) == expected_checked
        assert switches[switch_id]["onchange"] == (
            f"toggleAdmin({user_ids[target_role]}, this.checked)"
        )
    assert "function toggleAdmin(" in response.text


@pytest.mark.parametrize(
    "expiration_type,never_expire,expected",
    [
        ("from_last_access", False, "days from last access)"),
        ("from_creation", False, "days from creation)"),
        ("from_last_access", True, "Never Expires"),
    ],
)
def test_comparison_expiration_labels_preserve_rendered_whitespace(
    client, expiration_type, never_expire, expected
):
    comparison_id = "88888888-8888-8888-8888-888888888888"
    database.create_comparison(
        comparison_id,
        "Comparison",
        None,
        [],
        {
            "total_rows": 1,
            "total_columns": 1,
            "expiration_days": 7,
            "expiration_type": expiration_type,
            "never_expire": never_expire,
        },
    )
    database.store_image_position(comparison_id, "image.png", 0, 0)
    response = client.get(f"/compare/{comparison_id}")
    assert response.status_code == 200
    assert expected in re.sub(r"\s+", " ", response.text)
