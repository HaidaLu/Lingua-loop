from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)

DEFAULT_DECKS = [
    ("new-en", "en"),
    ("new-de", "de"),
]


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _migrate() -> None:
    """Lightweight migration: add columns to an existing words table (create_all won't ALTER)."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        for column, ddl in (("deck_id", "INTEGER"), ("prompt", "TEXT"), ("youglish_term", "TEXT")):
            if not _column_exists(conn, "words", column):
                conn.execute(text(f"ALTER TABLE words ADD COLUMN {column} {ddl}"))


def _seed_decks() -> None:
    from app.models import Deck, Word  # noqa: F401

    with Session(engine) as session:
        existing = {d.name: d for d in session.query(Deck).all()}
        for name, lang in DEFAULT_DECKS:
            if name not in existing:
                session.add(Deck(name=name, language=lang, is_default=True))
        session.commit()

        # assign deckless legacy cards to the default deck for their language
        decks = {d.language: d for d in session.query(Deck).filter(Deck.is_default).all()}
        for w in session.query(Word).filter(Word.deck_id.is_(None)).all():
            d = decks.get(w.language)
            if d:
                w.deck_id = d.id
                session.add(w)
        session.commit()


def init_db() -> None:
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate()
    _seed_decks()
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
