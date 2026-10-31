"""Runs one collection cycle and exits, so the demo does not wait for the scheduler's timers.

Run from the ingestion/ folder. With --simulate-results it also asks the mock football API to
finish today's matches, then evaluates the stored predictions against those results.
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core import database
from app.core.config import settings
from app.core.scheduler import scheduler
from app.services.accuracy_evaluator import PredictionAccuracyEvaluator


async def main(simulate_results: bool) -> None:
    await scheduler.run_daily_collection()
    await scheduler._process_results_check()
    if simulate_results:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{settings.FOOTBALL_API_BASE_URL}/__finish-today")
            response.raise_for_status()
        db = database.SessionLocal()
        try:
            result = await PredictionAccuracyEvaluator(db).collect_and_evaluate_all(days_back=7)
            logging.getLogger(__name__).info("Accuracy evaluation: %s", result)
        finally:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulate-results", action="store_true")
    args = parser.parse_args()
    database.init_database()
    asyncio.run(main(args.simulate_results))
