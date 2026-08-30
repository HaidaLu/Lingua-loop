from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.time_utils import utcnow as _utcnow


class User(SQLModel, table=True):
    """Single-user login gate. Registration is only open while there are 0 users."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    created_at: datetime = Field(default_factory=_utcnow)


class Deck(SQLModel, table=True):
    """A deck (Anki-style). Default decks new-en / new-de cannot be deleted."""

    __tablename__ = "decks"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    language: str | None = None  # 'en' | 'de' | None (mixed)
    is_default: bool = False
    created_at: datetime = Field(default_factory=_utcnow)


class Word(SQLModel, table=True):
    """The vocabulary entry itself. Maps to the words table in PROJECT_SPEC §4."""

    __tablename__ = "words"
    __table_args__ = (UniqueConstraint("word", "language", name="uq_word_language"),)

    id: int | None = Field(default=None, primary_key=True)
    word: str = Field(index=True)  # the target-language headword (YouGlish / gender / dedup key)
    language: str = Field(index=True)  # 'en' | 'de'
    # clean single term to search on YouGlish; resolved lazily (LLM) for messy imported cards
    youglish_term: str | None = None
    deck_id: int | None = Field(default=None, foreign_key="decks.id", index=True)
    # optional custom review-front text (e.g. a native-language prompt); front = prompt or word
    prompt: str | None = None
    pos: str | None = None

    # array fields stored as JSON strings
    definitions: str = "[]"
    examples: str = "[]"
    collocations: str = "[]"

    # one concise gloss in the target language
    translation: str | None = None

    # German-only
    gender: str | None = None  # 'der' | 'die' | 'das'
    plural_form: str | None = None
    case_notes: str | None = None

    mnemonic: str | None = None
    source: str = "llm_lookup"  # 'manual' | 'llm_lookup' | 'nicos_weg_dictation'
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class FsrsCard(SQLModel, table=True):
    """One FSRS review state per word. Maps to the fsrs_cards table in PROJECT_SPEC §4."""

    __tablename__ = "fsrs_cards"

    id: int | None = Field(default=None, primary_key=True)
    word_id: int = Field(foreign_key="words.id", unique=True, index=True)

    state: str = "new"  # 'new' | 'learning' | 'review' | 'relearning'
    stability: float | None = None
    difficulty: float | None = None
    due_date: datetime = Field(default_factory=_utcnow, index=True)
    reps: int = 0
    lapses: int = 0
    last_review: datetime | None = None

    # full py-fsrs Card.to_dict() serialization — the source of truth for algorithm state
    card_json: str = "{}"

    created_at: datetime = Field(default_factory=_utcnow)


class ReviewLog(SQLModel, table=True):
    """One row per review grade, written by the review flow."""

    __tablename__ = "review_logs"

    id: int | None = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="fsrs_cards.id", index=True)
    rating: int  # 1=again 2=hard 3=good 4=easy
    reviewed_at: datetime = Field(default_factory=_utcnow)


class MediaFile(SQLModel, table=True):
    """An audio (or other) file attached to a word: imported from Anki, or a user recording."""

    __tablename__ = "media"

    id: int | None = Field(default=None, primary_key=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    kind: str  # 'word' | 'example' | 'extra' | 'user_recording'
    filename: str  # stored file name, relative to settings.media_dir
    mime: str
    source: str = "anki_import"  # 'anki_import' | 'recording'
    created_at: datetime = Field(default_factory=_utcnow)
