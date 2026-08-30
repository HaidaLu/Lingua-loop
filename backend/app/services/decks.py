from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Deck, FsrsCard, ReviewLog, Word
from app.schemas import DeckOut
from app.time_utils import utcnow

_DEFAULT_NAME = {"en": "new-en", "de": "new-de"}


def get_or_create_default(session: Session, language: str) -> Deck:
    name = _DEFAULT_NAME.get(language, f"new-{language}")
    deck = session.exec(select(Deck).where(Deck.name == name)).first()
    if deck is None:
        deck = Deck(name=name, language=language, is_default=True)
        session.add(deck)
        session.commit()
        session.refresh(deck)
    return deck


def resolve_deck(session: Session, *, deck_id: int | None, language: str) -> Deck:
    """Pick the deck for a new card: explicit deck_id wins, else the default deck for the language."""
    if deck_id is not None:
        deck = session.get(Deck, deck_id)
        if deck is None:
            raise HTTPException(status_code=404, detail="deck not found")
        return deck
    return get_or_create_default(session, language)


def list_decks(session: Session) -> list[DeckOut]:
    now = utcnow()

    def _grouped(*conds) -> dict[int, int]:
        stmt = (
            select(Word.deck_id, func.count())
            .join(FsrsCard, FsrsCard.word_id == Word.id)
            .group_by(Word.deck_id)
        )
        for c in conds:
            stmt = stmt.where(c)
        return dict(session.exec(stmt).all())

    counts = dict(
        session.exec(select(Word.deck_id, func.count()).group_by(Word.deck_id)).all()
    )
    new_c = _grouped(FsrsCard.state == "new")
    learn_c = _grouped(
        FsrsCard.state.in_(("learning", "relearning")), FsrsCard.due_date <= now
    )
    due_c = _grouped(FsrsCard.state == "review", FsrsCard.due_date <= now)

    out = []
    for d in session.exec(select(Deck).order_by(Deck.is_default.desc(), Deck.name)).all():
        out.append(
            DeckOut(
                id=d.id,
                name=d.name,
                language=d.language,
                is_default=d.is_default,
                card_count=counts.get(d.id, 0),
                new_count=new_c.get(d.id, 0),
                learn_count=learn_c.get(d.id, 0),
                due_count=due_c.get(d.id, 0),
            )
        )
    return out


def create_deck(session: Session, *, name: str, language: str | None) -> Deck:
    name = name.strip()
    if session.exec(select(Deck).where(Deck.name == name)).first():
        raise HTTPException(status_code=409, detail="A deck with that name already exists")
    deck = Deck(name=name, language=language, is_default=False)
    session.add(deck)
    session.commit()
    session.refresh(deck)
    return deck


def rename_deck(session: Session, deck_id: int, name: str) -> Deck:
    deck = session.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="deck not found")
    if deck.is_default:
        raise HTTPException(status_code=400, detail="Default decks can't be renamed")
    name = name.strip()
    clash = session.exec(select(Deck).where(Deck.name == name, Deck.id != deck_id)).first()
    if clash:
        raise HTTPException(status_code=409, detail="A deck with that name already exists")
    deck.name = name
    session.add(deck)
    session.commit()
    session.refresh(deck)
    return deck


def delete_deck(session: Session, deck_id: int, *, keep_cards: bool = False) -> None:
    deck = session.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="deck not found")
    if deck.is_default:
        raise HTTPException(status_code=400, detail="Default decks can't be deleted")

    words = session.exec(select(Word).where(Word.deck_id == deck_id)).all()
    if keep_cards:
        # move cards to the default deck for their language
        for w in words:
            w.deck_id = get_or_create_default(session, w.language).id
            session.add(w)
    else:
        # delete the cards and their review history + media (Anki-style)
        from app.services import media as media_svc

        for w in words:
            media_svc.delete_for_word(session, w.id)
            fc = session.exec(select(FsrsCard).where(FsrsCard.word_id == w.id)).first()
            if fc is not None:
                for log in session.exec(
                    select(ReviewLog).where(ReviewLog.card_id == fc.id)
                ).all():
                    session.delete(log)
                session.delete(fc)
            session.delete(w)
    session.delete(deck)
    session.commit()
