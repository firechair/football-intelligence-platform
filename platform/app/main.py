"""Entrypoint for the published modules: accounts and bookmaker analytics.

New in this repository. The original entrypoint also mounted the chat and football routers,
which stay private.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import intelligent_odds, users
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Football intelligence platform", lifespan=lifespan)

app.include_router(users.router, prefix="/api")
app.include_router(intelligent_odds.router)


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}
