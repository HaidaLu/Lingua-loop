from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlmodel import Session

from app.auth import get_current_user
from app.db import get_session
from app.schemas import (
    CardCreate,
    GenerateCardRequest,
    GenerateCardResponse,
    MediaOut,
    WordListResponse,
    WordUpdate,
    YouglishTermResponse,
)
from app.services import cards
from app.services import media as media_svc

router = APIRouter(prefix="/api", tags=["cards"], dependencies=[Depends(get_current_user)])


@router.post("/generate-card", response_model=GenerateCardResponse)
def generate_card(req: GenerateCardRequest, session: Session = Depends(get_session)):
    try:
        return cards.generate_card(
            session,
            word=req.word,
            language=req.language,
            context=req.context,
            deck_id=req.deck_id,
            use_query_as_prompt=req.use_query_as_prompt,
        )
    except HTTPException:
        raise
    except Exception as e:  # LLM call failed, etc.
        raise HTTPException(status_code=502, detail=f"Card generation failed: {e}") from e


@router.get("/words", response_model=WordListResponse)
def list_words(
    language: str | None = Query(default=None, pattern="^(en|de)$"),
    deck_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    return cards.list_words(
        session, language=language, deck_id=deck_id, q=q, offset=offset, limit=limit
    )


@router.post("/cards", response_model=GenerateCardResponse, status_code=201)
def create_card(req: CardCreate, session: Session = Depends(get_session)):
    return cards.create_manual(session, req)


@router.get("/cards/{word_id}", response_model=GenerateCardResponse)
def get_card(word_id: int, session: Session = Depends(get_session)):
    return cards.get_word(session, word_id)


@router.patch("/cards/{word_id}", response_model=GenerateCardResponse)
def edit_card(word_id: int, patch: WordUpdate, session: Session = Depends(get_session)):
    return cards.update_word(session, word_id, patch)


@router.post("/cards/{word_id}/youglish-term", response_model=YouglishTermResponse)
def youglish_term(word_id: int, session: Session = Depends(get_session)):
    return cards.resolve_youglish_term(session, word_id)


@router.delete("/cards/{word_id}", status_code=204)
def remove_card(word_id: int, session: Session = Depends(get_session)):
    cards.delete_word(session, word_id)
    return Response(status_code=204)


@router.post("/cards/{word_id}/recordings", response_model=MediaOut, status_code=201)
async def add_recording(
    word_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty recording")
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="recording too large (limit 15 MB)")
    return media_svc.add_recording(session, word_id, data, file.content_type or "audio/webm")


@router.post("/cards/{word_id}/media", response_model=MediaOut, status_code=201)
async def add_media(
    word_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > 60 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large (limit 60 MB)")
    return media_svc.add_attachment(
        session, word_id, data, file.content_type or "", file.filename
    )
