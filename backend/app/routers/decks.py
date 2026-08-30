from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session

from app.auth import get_current_user
from app.db import get_session
from app.schemas import DeckCreate, DeckOut, DeckUpdate
from app.services import decks

router = APIRouter(
    prefix="/api/decks", tags=["decks"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[DeckOut])
def list_decks(session: Session = Depends(get_session)):
    return decks.list_decks(session)


@router.post("", response_model=DeckOut, status_code=201)
def create_deck(req: DeckCreate, session: Session = Depends(get_session)):
    decks.create_deck(session, name=req.name, language=req.language)
    return next(d for d in decks.list_decks(session) if d.name == req.name.strip())


@router.patch("/{deck_id}", response_model=DeckOut)
def rename_deck(deck_id: int, req: DeckUpdate, session: Session = Depends(get_session)):
    d = decks.rename_deck(session, deck_id, req.name)
    return next(x for x in decks.list_decks(session) if x.id == d.id)


@router.delete("/{deck_id}", status_code=204)
def delete_deck(
    deck_id: int,
    keep_cards: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    decks.delete_deck(session, deck_id, keep_cards=keep_cards)
    return Response(status_code=204)
