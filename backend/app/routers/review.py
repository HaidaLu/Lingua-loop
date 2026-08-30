from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.auth import get_current_user
from app.db import get_session
from app.schemas import (
    DueQueueResponse,
    HeatmapResponse,
    ReviewStats,
    ReviewSubmitRequest,
    ReviewSubmitResponse,
)
from app.services import review

router = APIRouter(
    prefix="/api/review", tags=["review"], dependencies=[Depends(get_current_user)]
)


@router.get("/due", response_model=DueQueueResponse)
def due(
    language: str | None = Query(default=None, pattern="^(en|de)$"),
    deck_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    return review.due_queue(session, language=language, deck_id=deck_id, limit=limit)


@router.post("/submit", response_model=ReviewSubmitResponse)
def submit(req: ReviewSubmitRequest, session: Session = Depends(get_session)):
    return review.submit(session, word_id=req.word_id, rating=req.rating)


@router.get("/stats", response_model=ReviewStats)
def stats(session: Session = Depends(get_session)):
    return review.stats(session)


@router.get("/heatmap", response_model=HeatmapResponse)
def heatmap(
    days: int = Query(default=365, ge=30, le=366),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
    session: Session = Depends(get_session),
):
    return review.heatmap(session, days=days, tz_offset_minutes=tz_offset_minutes)
