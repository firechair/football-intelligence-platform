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
