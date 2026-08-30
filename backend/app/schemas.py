from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Language = Literal["en", "de"]


# ============ auth ============
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


class AuthStatus(BaseModel):
    registered: bool  # whether an account exists (frontend shows login vs register)


# ============ decks ============
class DeckOut(BaseModel):
    id: int
    name: str
    language: str | None
    is_default: bool
    card_count: int
    new_count: int          # cards never studied
    learn_count: int        # learning / relearning cards due now
    due_count: int          # review-state cards due now


class DeckCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    language: Language | None = None


class DeckUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


# ============ cards ============
class CardCreate(BaseModel):
    """Manual card creation — no LLM. Like Anki's Add dialog."""

    deck_id: int | None = None  # omit -> default deck for the language
    language: Language
    word: str = Field(min_length=1, max_length=200)
    prompt: str | None = None
    pos: str | None = None
    translation: str | None = None
    definitions: list[str] = []
    examples: list[str] = []
    collocations: list[str] = []
    gender: Literal["der", "die", "das"] | None = None
    plural_form: str | None = None
    case_notes: str | None = None
    mnemonic: str | None = None


class GenerateCardRequest(BaseModel):
    word: str = Field(min_length=1, max_length=200)  # may be Chinese / a synonym / an inflected form
    language: Language
    context: str | None = Field(default=None, max_length=2000)
    deck_id: int | None = None  # omit -> default deck for the language (new-en / new-de)
    # when the search text was in another language, keep it as the card's review-front prompt
    use_query_as_prompt: bool = True


class LLMCard(BaseModel):
    # the canonical dictionary form in the target language (verb infinitive, singular noun, ...)
    headword: str
    # was the user's search text already in the target language ("target") or another language ("other")
    query_language: Literal["target", "other"] = "target"
    pos: str | None = None
    translation: str | None = None  # one concise English gloss
    definitions: list[str] = []
    examples: list[str] = []
    collocations: list[str] = []
    gender: Literal["der", "die", "das"] | None = None
    plural_form: str | None = None
    case_notes: str | None = None
    mnemonic: str | None = None


class FsrsState(BaseModel):
    state: str
    due_date: datetime
    stability: float | None = None
    difficulty: float | None = None
    reps: int
    lapses: int
    last_review: datetime | None = None


class MediaOut(BaseModel):
    id: int
    kind: str  # 'word' | 'example' | 'extra' | 'user_recording'
    mime: str
    source: str  # 'anki_import' | 'recording'


class WordOut(BaseModel):
    id: int
    word: str
    language: str
    youglish_term: str | None = None
    deck_id: int | None
    deck_name: str | None
    prompt: str | None
    media: list[MediaOut] = []
    pos: str | None
    translation: str | None
    definitions: list[str]
    examples: list[str]
    collocations: list[str]
    gender: str | None
    plural_form: str | None
    case_notes: str | None
    mnemonic: str | None
    source: str
    created_at: datetime
    updated_at: datetime


class GenerateCardResponse(BaseModel):
    word: WordOut
    fsrs: FsrsState
    llm_provider: str
    created: bool


class WordUpdate(BaseModel):
    word: str | None = Field(default=None, min_length=1, max_length=200)
    deck_id: int | None = None
    prompt: str | None = None
    pos: str | None = None
    translation: str | None = None
    definitions: list[str] | None = None
    examples: list[str] | None = None
    collocations: list[str] | None = None
    gender: Literal["der", "die", "das"] | None = None
    plural_form: str | None = None
    case_notes: str | None = None
    mnemonic: str | None = None


class WordListResponse(BaseModel):
    items: list[WordOut]
    total: int
    offset: int
    limit: int


class YouglishTermResponse(BaseModel):
    term: str
    # "stored": already resolved before; "word": card word was clean enough to use as-is;
    # "llm": resolved from a messy word by the LLM; "fallback": LLM failed, sanitized word
    resolved_by: Literal["stored", "word", "llm", "fallback"]


# ============ review ============
class ReviewItem(BaseModel):
    word: WordOut
    fsrs: FsrsState


class DueQueueResponse(BaseModel):
    items: list[ReviewItem]
    total_due: int


class ReviewSubmitRequest(BaseModel):
    word_id: int
    rating: Literal[1, 2, 3, 4]


class ReviewSubmitResponse(BaseModel):
    word_id: int
    fsrs: FsrsState


class ReviewStats(BaseModel):
    total_cards: int
    new_cards: int          # cards never studied
    learn_now: int          # learning / relearning cards due now
    due_now: int            # review-state cards due now
    reviewed_today: int
    by_language: dict[str, int]


# ============ heatmap ============
class HeatmapDay(BaseModel):
    date: str  # YYYY-MM-DD (in the user's local timezone)
    count: int  # activity that day = reviews + added
    reviews: int
    added: int


class HeatmapResponse(BaseModel):
    days: list[HeatmapDay]
    current_streak: int
    longest_streak: int
    active_days: int
    total_reviews: int


# ============ anki import ============
class AnkiNoteType(BaseModel):
    name: str
    fields: list[str]
    note_count: int


class AnkiSample(BaseModel):
    note_type: str
    fields: dict[str, str]


class AnkiPreviewResponse(BaseModel):
    import_id: str
    note_types: list[AnkiNoteType]
    anki_decks: list[str]
    total_notes: int
    notes_with_progress: int
    samples: list[AnkiSample]
    suggested_deck_name: str


class AnkiCommitRequest(BaseModel):
    import_id: str
    deck_name: str = Field(min_length=1, max_length=60)
    language: Language
    note_type: str
    word_field: str
    word_extract: Literal["whole", "before_separator"] = "whole"
    prompt_field: str | None = None
    meaning_field: str | None = None
    examples_field: str | None = None
    import_progress: bool = True
    on_duplicate: Literal["skip", "overwrite"] = "skip"


class AnkiCommitResponse(BaseModel):
    deck_id: int
    deck_name: str
    imported: int
    updated: int
    skipped: int
