from __future__ import annotations

import json
import re

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.llm import get_generator
from app.models import Deck, FsrsCard, ReviewLog, Word
from app.schemas import (
    CardCreate,
    FsrsState,
    GenerateCardResponse,
    LLMCard,
    MediaOut,
    WordListResponse,
    WordOut,
    WordUpdate,
    YouglishTermResponse,
)
from app.services import decks as deck_svc
from app.services import fsrs
from app.services import media as media_svc
from app.time_utils import utcnow


def _deck_names(session: Session) -> dict[int, str]:
    return {d.id: d.name for d in session.exec(select(Deck)).all()}


def word_out(
    w: Word, deck_name: str | None = None, media: list[MediaOut] | None = None
) -> WordOut:
    return WordOut(
        id=w.id,
        word=w.word,
        language=w.language,
        youglish_term=w.youglish_term,
        deck_id=w.deck_id,
        deck_name=deck_name,
        prompt=w.prompt,
        media=media or [],
        pos=w.pos,
        translation=w.translation,
        definitions=json.loads(w.definitions),
        examples=json.loads(w.examples),
        collocations=json.loads(w.collocations),
        gender=w.gender,
        plural_form=w.plural_form,
        case_notes=w.case_notes,
        mnemonic=w.mnemonic,
        source=w.source,
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


def fsrs_state(c: FsrsCard) -> FsrsState:
    return FsrsState(
        state=c.state,
        due_date=c.due_date,
        stability=c.stability,
        difficulty=c.difficulty,
        reps=c.reps,
        lapses=c.lapses,
        last_review=c.last_review,
    )


def _apply_llm_card(w: Word, card: LLMCard, *, source: str) -> None:
    w.pos = card.pos
    w.translation = card.translation
    w.definitions = json.dumps(card.definitions, ensure_ascii=False)
    w.examples = json.dumps(card.examples, ensure_ascii=False)
    w.collocations = json.dumps(card.collocations, ensure_ascii=False)
    w.gender = card.gender
    w.plural_form = card.plural_form
    w.case_notes = card.case_notes
    w.mnemonic = card.mnemonic
    w.source = source
    w.updated_at = utcnow()


def generate_card(
    session: Session,
    *,
    word: str,
    language: str,
    context: str | None = None,
    deck_id: int | None = None,
    use_query_as_prompt: bool = True,
) -> GenerateCardResponse:
    """Look up -> LLM resolves the query to a headword + English card -> upsert words -> init fsrs_cards."""
    query = word.strip()
    deck = deck_svc.resolve_deck(session, deck_id=deck_id, language=language)

    generator = get_generator()
    llm_card = generator.generate(query, language, context)

    headword = (llm_card.headword or query).strip()
    cross_language = (
        llm_card.query_language == "other" and query.casefold() != headword.casefold()
    )
    prompt = query if (use_query_as_prompt and cross_language) else None

    existing = session.exec(
        select(Word).where(Word.word == headword, Word.language == language)
    ).first()

    created = existing is None
    w = existing or Word(word=headword, language=language)
    _apply_llm_card(w, llm_card, source="llm_lookup")
    if prompt and (created or not w.prompt):
        w.prompt = prompt
    if created or w.deck_id is None:
        w.deck_id = deck.id
    elif deck_id is not None:  # only move an existing card when a deck was explicitly given
        w.deck_id = deck.id
    session.add(w)
    session.commit()
    session.refresh(w)

    fcard = session.exec(select(FsrsCard).where(FsrsCard.word_id == w.id)).first()
    if fcard is None:
        fcard = FsrsCard(word_id=w.id, **fsrs.new_card())
        session.add(fcard)
        session.commit()
        session.refresh(fcard)

    return GenerateCardResponse(
        word=word_out(
            w,
            session.get(Deck, w.deck_id).name if w.deck_id else None,
            media_svc.list_for_word(session, w.id),
        ),
        fsrs=fsrs_state(fcard),
        llm_provider=generator.name,
        created=created,
    )


def create_manual(session: Session, data: CardCreate) -> GenerateCardResponse:
    """Create a card by hand (no LLM). source='manual'."""
    word = data.word.strip()
    deck = deck_svc.resolve_deck(session, deck_id=data.deck_id, language=data.language)

    existing = session.exec(
        select(Word).where(Word.word == word, Word.language == data.language)
    ).first()
    if existing is not None:
        dname = session.get(Deck, existing.deck_id).name if existing.deck_id else "?"
        raise HTTPException(
            status_code=409, detail=f'"{word}" ({data.language}) already exists in deck "{dname}"'
        )

    w = Word(
        word=word,
        language=data.language,
        deck_id=deck.id,
        prompt=(data.prompt or "").strip() or None,
        pos=data.pos,
        translation=data.translation,
        definitions=json.dumps(data.definitions, ensure_ascii=False),
        examples=json.dumps(data.examples, ensure_ascii=False),
        collocations=json.dumps(data.collocations, ensure_ascii=False),
        gender=data.gender,
        plural_form=data.plural_form,
        case_notes=data.case_notes,
        mnemonic=data.mnemonic,
        source="manual",
    )
    session.add(w)
    session.flush()
    session.add(FsrsCard(word_id=w.id, **fsrs.new_card()))
    session.commit()
    session.refresh(w)
    return get_word(session, w.id)


def list_words(
    session: Session,
    *,
    language: str | None = None,
    deck_id: int | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> WordListResponse:
    where = []
    if language:
        where.append(Word.language == language)
    if deck_id is not None:
        where.append(Word.deck_id == deck_id)
    if q:
        where.append(Word.word.ilike(f"%{q.strip()}%"))

    count_stmt = select(func.count()).select_from(Word)
    page_stmt = select(Word).order_by(Word.updated_at.desc()).offset(offset).limit(limit)
    for cond in where:
        count_stmt = count_stmt.where(cond)
        page_stmt = page_stmt.where(cond)

    names = _deck_names(session)
    total = session.exec(count_stmt).one()
    words = session.exec(page_stmt).all()
    media = media_svc.by_words(session, [w.id for w in words])
    items = [word_out(w, names.get(w.deck_id), media.get(w.id)) for w in words]
    return WordListResponse(items=items, total=total, offset=offset, limit=limit)


def get_word(session: Session, word_id: int) -> GenerateCardResponse:
    w = session.get(Word, word_id)
    if w is None:
        raise HTTPException(status_code=404, detail="word not found")
    fcard = session.exec(select(FsrsCard).where(FsrsCard.word_id == w.id)).first()
    deck_name = session.get(Deck, w.deck_id).name if w.deck_id else None
    return GenerateCardResponse(
        word=word_out(w, deck_name, media_svc.list_for_word(session, w.id)),
        fsrs=fsrs_state(fcard)
        if fcard
        else FsrsState(state="new", due_date=w.created_at, reps=0, lapses=0),
        llm_provider="-",
        created=False,
    )


def update_word(session: Session, word_id: int, patch: WordUpdate) -> GenerateCardResponse:
    w = session.get(Word, word_id)
    if w is None:
        raise HTTPException(status_code=404, detail="word not found")

    data = patch.model_dump(exclude_unset=True)
    for field in ("word", "prompt", "pos", "translation", "gender", "plural_form", "case_notes", "mnemonic"):
        if field in data:
            value = data[field]
            if field == "prompt" and isinstance(value, str) and not value.strip():
                value = None
            setattr(w, field, value)
    for field in ("definitions", "examples", "collocations"):
        if field in data and data[field] is not None:
            setattr(w, field, json.dumps(data[field], ensure_ascii=False))
    if "deck_id" in data and data["deck_id"] is not None:
        if session.get(Deck, data["deck_id"]) is None:
            raise HTTPException(status_code=404, detail="deck not found")
        w.deck_id = data["deck_id"]
    w.source = "manual" if w.source == "llm_lookup" else w.source
    w.updated_at = utcnow()
    session.add(w)
    session.commit()
    session.refresh(w)
    return get_word(session, word_id)


# ---- YouGlish search term ----

_YG_PUNCT = re.compile(r"""[.!?;:,/()\[\]{}"'|<>*]""")
_CJK = re.compile(r"[㐀-鿿]")


def _sanitize_term(raw: str) -> str:
    text = (raw or "").split("\n", 1)[0].strip()
    text = re.sub(r"\s+", " ", text)
    # drop a trailing German article marker like ", der" / " – die"
    text = re.sub(r"\s*[,–—-]\s*(der|die|das)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[^\w]+|[^\w]+$", "", text)  # trim leading/trailing punctuation
    return text.strip()


def _term_looks_messy(term: str) -> bool:
    if not term:
        return True
    if _YG_PUNCT.search(term) or _CJK.search(term):
        return True
    return len(term) > 40 or len(term.split()) > 3


def resolve_youglish_term(session: Session, word_id: int) -> YouglishTermResponse:
    """Best clean term to feed YouGlish for this card, cached on the row.

    Clean words (our own cards, tidy imports) are used as-is. Messy ones — full
    phrases / Chinese / punctuation, typical of Anki imports — are resolved to a
    canonical target-language headword by the LLM.
    """
    w = session.get(Word, word_id)
    if w is None:
        raise HTTPException(status_code=404, detail="word not found")

    if w.youglish_term:
        return YouglishTermResponse(term=w.youglish_term, resolved_by="stored")

    sanitized = _sanitize_term(w.word)

    if not _term_looks_messy(sanitized):
        w.youglish_term = sanitized
        w.updated_at = utcnow()
        session.add(w)
        session.commit()
        return YouglishTermResponse(term=sanitized, resolved_by="word")

    examples = json.loads(w.examples or "[]")
    context = examples[0] if examples else (w.translation or None)
    try:
        card = get_generator().generate(w.word, w.language, context)
        term = _sanitize_term(card.headword) or sanitized
        if _term_looks_messy(term):
            raise ValueError("llm headword still not usable")
        w.youglish_term = term
        w.updated_at = utcnow()
        session.add(w)
        session.commit()
        return YouglishTermResponse(term=term, resolved_by="llm")
    except Exception:
        fallback = sanitized or re.sub(r"\s+", " ", w.word.strip())[:50]
        return YouglishTermResponse(term=fallback, resolved_by="fallback")


def delete_word(session: Session, word_id: int) -> None:
    w = session.get(Word, word_id)
    if w is None:
        raise HTTPException(status_code=404, detail="word not found")
    media_svc.delete_for_word(session, word_id)
    fcard = session.exec(select(FsrsCard).where(FsrsCard.word_id == word_id)).first()
    if fcard is not None:
        for log in session.exec(select(ReviewLog).where(ReviewLog.card_id == fcard.id)).all():
            session.delete(log)
        session.delete(fcard)
    session.delete(w)
    session.commit()
