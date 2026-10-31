import asyncio
import time

import httpx
import respx

from app.core.config import settings
from app.utils import football_api
from app.utils.football_api import FootballAPIClient


async def test_concurrent_requests_respect_spacing(monkeypatch):
    monkeypatch.setattr(football_api, "_request_spacing", 0.2)
    monkeypatch.setattr(football_api, "_last_request_time", 0)
    started = []

    def record(request):
        started.append(time.monotonic())
        return httpx.Response(200, json={"response": []})

    with respx.mock:
        respx.get(f"{settings.FOOTBALL_API_BASE_URL}/status").mock(side_effect=record)
        client = FootballAPIClient()
        await asyncio.gather(*(client._make_request("status") for _ in range(10)))

    gaps = [later - earlier for earlier, later in zip(sorted(started), sorted(started)[1:])]
    assert len(started) == 10
    # Half the spacing: creating each httpx client adds some jitter, a burst gives gaps close to zero.
    assert min(gaps) >= 0.1, f"requests started in bursts: smallest gap {min(gaps):.3f}s"
