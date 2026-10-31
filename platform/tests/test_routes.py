from app.main import app


def test_user_admin_routes_removed():
    paths = set(app.openapi()["paths"])
    assert "/api/users/list" not in paths
    assert "/api/users/cleanup-except-firechair" not in paths


def test_account_routes_still_mounted():
    paths = set(app.openapi()["paths"])
    assert {"/api/users/register", "/api/users/login", "/health"} <= paths
