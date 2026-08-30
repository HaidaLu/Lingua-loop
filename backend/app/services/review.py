from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Deck, FsrsCard, ReviewLog, Word
from app.schemas import (
    DueQueueResponse,
    HeatmapDay,
    HeatmapResponse,
    ReviewItem,
    ReviewStats,
    ReviewSubmitResponse,
)
from app.services import fsrs
from app.services import media as media_svc
from app.services.cards import fsrs_state, word_out
from app.time_utils import utcnow


def due_queue(
    session: Session,
    *,
    language: str | None = None,
    deck_id: int | None = None,
    limit: int = 50,
) -> DueQueueResponse:
    now = utcnow()
    conds = [FsrsCard.due_date <= now]
    if language:
        conds.append(Word.language == language)
    if deck_id is not None:
        conds.append(Word.deck_id == deck_id)

    count_stmt = select(func.count()).select_from(FsrsCard).join(Word, Word.id == FsrsCard.word_id)
    page_stmt = (
        select(FsrsCard, Word)
        .join(Word, Word.id == FsrsCard.word_id)
        .order_by(FsrsCard.due_date.asc())
        .limit(limit)
    )
    for c in conds:
        count_stmt = count_stmt.where(c)
        page_stmt = page_stmt.where(c)

    names = {d.id: d.name for d in session.exec(select(Deck)).all()}
    total = session.exec(count_stmt).one()
    rows = session.exec(page_stmt).all()
    media = media_svc.by_words(session, [w.id for _c, w in rows])
    items = [
        ReviewItem(word=word_out(w, names.get(w.deck_id), media.get(w.id)), fsrs=fsrs_state(c))
        for c, w in rows
    ]
    return DueQueueResponse(items=items, total_due=total)


def submit(session: Session, *, word_id: int, rating: int) -> ReviewSubmitResponse:
    card = session.exec(select(FsrsCard).where(FsrsCard.word_id == word_id)).first()
    if card is None:
        raise HTTPException(status_code=404, detail="fsrs card not found for word")

    updated = fsrs.review(card.card_json, rating)
    card.state = updated["state"]
    card.stability = updated["stability"]
    card.difficulty = updated["difficulty"]
    card.due_date = updated["due_date"]
    card.last_review = updated["last_review"]
    card.card_json = updated["card_json"]
    card.reps += 1
    if rating == 1:
        card.lapses += 1
    session.add(card)
    session.add(ReviewLog(card_id=card.id, rating=rating))
    session.commit()
    session.refresh(card)
    return ReviewSubmitResponse(word_id=word_id, fsrs=fsrs_state(card))


def stats(session: Session) -> ReviewStats:
    now = utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total = session.exec(select(func.count()).select_from(FsrsCard)).one()
    new_cards = session.exec(
        select(func.count()).select_from(FsrsCard).where(FsrsCard.state == "new")
    ).one()
    learn_now = session.exec(
        select(func.count())
        .select_from(FsrsCard)
        .where(FsrsCard.state.in_(("learning", "relearning")), FsrsCard.due_date <= now)
    ).one()
    due_now = session.exec(
        select(func.count())
        .select_from(FsrsCard)
        .where(FsrsCard.state == "review", FsrsCard.due_date <= now)
    ).one()
    reviewed_today = session.exec(
        select(func.count()).select_from(ReviewLog).where(ReviewLog.reviewed_at >= day_start)
    ).one()
    lang_rows = session.exec(select(Word.language, func.count()).group_by(Word.language)).all()

    return ReviewStats(
        total_cards=total,
        new_cards=new_cards,
        learn_now=learn_now,
        due_now=due_now,
        reviewed_today=reviewed_today,
        by_language={lang: n for lang, n in lang_rows},
    )


def heatmap(session: Session, *, days: int = 365, tz_offset_minutes: int = 0) -> HeatmapResponse:
    """GitHub-style activity grid. A day counts as active if a card was reviewed or added that day."""
    shift = f"{tz_offset_minutes} minutes"
    today_local = (utcnow() + timedelta(minutes=tz_offset_minutes)).date()
    start_local = today_local - timedelta(days=days - 1)
    # UTC lower bound (local window start converted back to UTC, with one extra day of slack)
    utc_lo = datetime.combine(start_local, datetime.min.time()) - timedelta(minutes=tz_offset_minutes) - timedelta(days=1)

    rev_day = func.date(func.datetime(ReviewLog.reviewed_at, shift))
    rev_rows = dict(
        session.exec(
            select(rev_day, func.count())
            .where(ReviewLog.reviewed_at >= utc_lo)
            .group_by(rev_day)
        ).all()
    )
    add_day = func.date(func.datetime(Word.created_at, shift))
    add_rows = dict(
        session.exec(
            select(add_day, func.count())
            .where(Word.created_at >= utc_lo)
            .group_by(add_day)
        ).all()
    )

    out: list[HeatmapDay] = []
    for i in range(days):
        d = start_local + timedelta(days=i)
        key = d.isoformat()
        r = int(rev_rows.get(key, 0))
        a = int(add_rows.get(key, 0))
        out.append(HeatmapDay(date=key, count=r + a, reviews=r, added=a))

    # streak: consecutive active days counting back from today
    active = [day.count > 0 for day in out]
    current = 0
    for ok in reversed(active):
        if ok:
            current += 1
        else:
            break
    longest = cur = 0
    for ok in active:
        cur = cur + 1 if ok else 0
        longest = max(longest, cur)

    return HeatmapResponse(
        days=out,
        current_streak=current,
        longest_streak=longest,
        active_days=sum(active),
        total_reviews=sum(day.reviews for day in out),
    )
