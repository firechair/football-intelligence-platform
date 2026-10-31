import httpx
import respx

from app.core.config import settings


def test_live_endpoint_uses_configured_url_and_key(client):
    with respx.mock:
        route = respx.get(f"{settings.FOOTBALL_API_BASE_URL}/fixtures").mock(
            return_value=httpx.Response(200, json={"response": []})
        )
        response = client.get("/api/v1/fixtures/live")

    assert response.status_code == 200
    assert route.called
    assert route.calls[0].request.headers["x-apisports-key"] == settings.FOOTBALL_API_KEY


async def test_api_fixture_is_converted_to_a_response(db_session):
    from app.api.fixtures import _convert_api_fixture_to_frontend

    response = await _convert_api_fixture_to_frontend(
        {
            "fixture": {"id": 7, "date": "2026-10-31T20:45:00+00:00", "status": {"short": "NS", "long": "Not Started"}},
            "league": {"id": 135, "name": "Serie A", "logo": None},
            "teams": {"home": {"name": "Inter", "logo": None}, "away": {"name": "AC Milan", "logo": None}},
        },
        db_session,
    )
    assert response.fixture_id == 7
