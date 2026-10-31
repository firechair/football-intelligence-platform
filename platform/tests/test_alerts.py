from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.db import models
from app.services import alert_engine as alert_module
from app.services import bookmaker_analytics as analytics_module
from app.services import intelligent_cache as cache_module


@pytest.fixture
def services_use_test_db(db_session, monkeypatch):
    """Services open their own session with next(get_db()), so that is what gets replaced."""

    class Uncloseable:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            pass

    def fake_get_db():
        yield Uncloseable()

    monkeypatch.setattr(alert_module, "get_db", fake_get_db)
    monkeypatch.setattr(analytics_module, "get_db", fake_get_db)
    monkeypatch.setattr(cache_module, "get_db", fake_get_db)
    return db_session


def add_odds(db, *values):
    now = datetime.utcnow()
    for index, value in enumerate(values):
        db.add(
            models.OddsHistory(
                fixture_id=1,
                market_name="1X2",
                bookmaker="Bookmaker A",
                odd_value=Decimal(str(value)),
                timestamp=now - timedelta(minutes=30 - index * 10),
            )
        )
    db.commit()


async def test_detects_odds_move_above_threshold(services_use_test_db):
    add_odds(services_use_test_db, 2.00, 2.30)
    movements = await alert_module.alert_engine._detect_odds_movements(min_change_threshold=0.10, time_window="1h")
    assert len(movements) == 1


async def test_ignores_odds_move_below_threshold(services_use_test_db):
    add_odds(services_use_test_db, 2.00, 2.05)
    movements = await alert_module.alert_engine._detect_odds_movements(min_change_threshold=0.10, time_window="1h")
    assert movements == []


def add_stats(db):
    for bookmaker, best in (("Bookmaker A", 80), ("Bookmaker B", 20)):
        db.add(
            models.BookmakerStats(
                bookmaker=bookmaker,
                sport="football",
                market_type="1X2",
                best_odds_count=best,
                total_markets=100,
                consistency_score=Decimal("0.80"),
                last_updated=datetime.utcnow(),
            )
        )
    db.commit()


async def test_rankings_from_stats(services_use_test_db):
    add_stats(services_use_test_db)
    rankings = await analytics_module.bookmaker_analytics.calculate_bookmaker_rankings("football", "30d")
    by_name = {row["bookmaker"]: row for row in rankings}
    assert by_name["Bookmaker A"]["win_rate"] > by_name["Bookmaker B"]["win_rate"]
    assert rankings[0]["bookmaker"] == "Bookmaker A"


def test_value_bet_alerts_are_not_offered():
    # Detection was never implemented: the stub always returned an empty list.
    assert not hasattr(alert_module.alert_engine, "check_value_bet_alerts")
    assert alert_module.alert_engine._validate_alert_criteria("value_bet", {"min_ev": 0.1}) is False


async def test_bookmaker_specials_do_not_invent_alerts(services_use_test_db):
    specials = await alert_module.alert_engine._detect_bookmaker_specials(
        ["Bookmaker A", "Bookmaker B"], ["football"], user_id=1
    )
    assert specials == []
