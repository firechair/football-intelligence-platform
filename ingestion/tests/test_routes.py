from app.main import app

REMOVED = {
    "/api/v1/db-test",
    "/api/v1/admin/job/results-check",
    "/api/v1/admin/job/predictions-update",
    "/api/v1/migrate",
    "/api/v1/init-database",
    "/api/v1/debug-fixtures",
    "/api/v1/test-api",
    "/api/v1/recreate-tables",
    "/api/v1/check-predictions-schema",
    "/api/v1/fix-schema",
}


def test_no_unprotected_admin_routes():
    paths = {route.path for route in app.routes}
    assert not paths & REMOVED
    assert not [path for path in paths if path.startswith("/api/v1/admin")]


def test_public_routes_still_mounted():
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/api/v1/accuracy/statistics/summary" in paths
