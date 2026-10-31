"""Needs Postgres and the mock football API: docker compose run --rm ingestion pytest -m integration"""
import os
import re

import httpx
import pytest
from sqlalchemy import func

from app.core import database
from app.core.config import settings
from app.core.scheduler import scheduler
from app.models import BookmakerInfo, ExtendedOddsHistory, FixtureTrackingStatus, MatchPredictions, PredictionAccuracy
from app.services.accuracy_evaluator import PredictionAccuracyEvaluator

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]


@pytest.fixture(scope="module")
def session():
    if os.environ["DATABASE_URL"].startswith("sqlite"):
        pytest.skip("needs the Postgres database from compose.yaml")
    database.init_database()
    db = database.SessionLocal()
    yield db
    db.close()


def count(db, model) -> int:
    return db.query(func.count()).select_from(model).scalar()


async def test_daily_collection_fills_tables(session):
    await scheduler.run_daily_collection()
    session.expire_all()
    assert count(session, FixtureTrackingStatus) > 0
    assert count(session, MatchPredictions) > 0
    assert count(session, ExtendedOddsHistory) > 0
    names = {name for (name,) in session.query(BookmakerInfo.name).all()}
    assert names and all(re.fullmatch(r"Bookmaker [A-C]", name) for name in names)


async def test_results_check_writes_accuracy(session):
    async with httpx.AsyncClient() as client:
        (await client.post(f"{settings.FOOTBALL_API_BASE_URL}/__finish-today")).raise_for_status()
    await PredictionAccuracyEvaluator(session).collect_and_evaluate_all(days_back=7)
    session.expire_all()
    assert count(session, PredictionAccuracy) > 0
    # The migrated column has no server default, so the evaluator must set it.
    assert session.query(PredictionAccuracy).filter(PredictionAccuracy.evaluated_at.is_(None)).count() == 0


async def test_no_429_during_collection():
    async with httpx.AsyncClient() as client:
        stats = (await client.get(f"{settings.FOOTBALL_API_BASE_URL}/__stats")).json()
    assert stats["requests"] > 0
    assert stats["rejected_429"] == 0
