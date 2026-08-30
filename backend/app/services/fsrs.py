"""py-fsrs wrapper. new_card() initializes state; review() applies a grade."""

from __future__ import annotations

import json

from fsrs import Card, Rating, Scheduler

from app.time_utils import to_naive_utc

_scheduler = Scheduler()


def card_fields(card: Card) -> dict:
    """Flatten a py-fsrs Card into FsrsCard columns (mirror columns + full card_json)."""
    state_name = card.state.name.lower() if hasattr(card.state, "name") else str(card.state).lower()
    return {
        "state": state_name,
        "stability": card.stability,
        "difficulty": card.difficulty,
        "due_date": to_naive_utc(card.due),
        "last_review": to_naive_utc(card.last_review),
        "card_json": json.dumps(card.to_dict(), default=str),
    }


def new_card() -> dict:
    """Newly looked-up word -> initial FSRS card state."""
    fields = card_fields(Card())
    fields["state"] = "new"  # not reviewed yet; record as 'new'
    fields["reps"] = 0
    fields["lapses"] = 0
    return fields


def review(card_json: str, rating: int) -> dict:
    """Apply one grade (1=again 2=hard 3=good 4=easy); return the updated card fields."""
    card = Card.from_dict(json.loads(card_json))
    updated, _log = _scheduler.review_card(card, Rating(rating))
    return card_fields(updated)
