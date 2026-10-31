"""Entrypoint for the published modules: accounts and bookmaker analytics.

New in this repository. The original entrypoint also mounted the chat and football routers,
which stay private.
"""
from fastapi import FastAPI

from app.api import intelligent_odds, users
from app.db.init_db import init_db

app = FastAPI(title="Football intelligence platform")

app.include_router(users.router, prefix="/api")
app.include_router(intelligent_odds.router)


@app.on_event("startup")
def create_tables() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}
