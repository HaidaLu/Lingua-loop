from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.llm import get_generator
from app.routers import auth, cards, decks, media, review
from app.routers import import_ as import_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_generator()  # initialise early + log the active generator
    yield


app = FastAPI(title="Lingua Loop API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(decks.router)
app.include_router(cards.router)
app.include_router(review.router)
app.include_router(import_router.router)
app.include_router(media.router)


@app.get("/api/health", tags=["health"])
def health():
    provider = settings.effective_provider
    model = None
    if provider == "claude":
        model = settings.llm_model
    elif provider == "openai":
        model = settings.openai_model
    return {"status": "ok", "llm_provider": provider, "llm_model": model}
