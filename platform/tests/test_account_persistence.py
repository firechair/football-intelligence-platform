"""Changes made through the authenticated user must reach the database."""
import pyotp

from app.db.models import User


def test_update_profile_is_saved(client, auth_headers, db_session, test_user):
    response = client.patch(
        "/api/users/profile", json={"full_name": "Renamed", "preferences": {"theme": "dark"}}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Renamed"
    db_session.expire_all()
    stored = db_session.get(User, test_user.id)
    assert stored.full_name == "Renamed"


def test_two_factor_setup_and_verify_enable_it(client, auth_headers, db_session, test_user):
    setup = client.post("/api/users/2fa/setup", json={"password": "testpassword123"}, headers=auth_headers)
    assert setup.status_code == 200, setup.text
    db_session.expire_all()
    stored = db_session.get(User, test_user.id)
    assert stored.two_factor_secret, "the secret returned to the user was not stored"

    code = pyotp.TOTP(stored.two_factor_secret).now()
    verify = client.post("/api/users/2fa/verify", json={"token": code}, headers=auth_headers)
    assert verify.status_code == 200, verify.text
    db_session.expire_all()
    assert db_session.get(User, test_user.id).two_factor_enabled is True


def test_refresh_returns_new_tokens(client, test_user_tokens):
    response = client.post("/api/users/refresh", json={"refresh_token": test_user_tokens["refresh_token"]})
    assert response.status_code == 200, response.text
