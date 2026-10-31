from app.main import app


def test_user_admin_routes_removed():
    paths = set(app.openapi()["paths"])
    assert "/api/users/list" not in paths
    assert "/api/users/cleanup-except-firechair" not in paths


def test_account_routes_still_mounted():
    paths = set(app.openapi()["paths"])
    assert {"/api/users/register", "/api/users/login", "/health"} <= paths


def test_debug_registration_route_is_gone():
    assert "/api/users/register-minimal" not in app.openapi()["paths"]


def test_registration_is_rate_limited(client):
    codes = [
        client.post(
            "/api/users/register",
            json={"username": f"user{i}", "email": f"user{i}@example.com", "password": "Str0ng-Passw0rd"},
        ).status_code
        for i in range(4)
    ]
    assert codes == [200, 200, 200, 429]
