# Backend — Lingua Loop

FastAPI + SQLModel/SQLite. Look up → LLM card generation → self-hosted FSRS store + review / card management.

## Run

```bash
cd backend
uv sync
# .env is preconfigured for DashScope (Qwen); to change the model see .env.example
uv run uvicorn app.main:app --reload --port 8000
```

Your data lives in `backend/language_learning.db` and persists across restarts. Back it up before
big changes: `cp language_learning.db language_learning.db.bak-$(date +%Y%m%d)`. Schema changes are
applied non-destructively on startup (`db.py::_migrate`).

- Swagger UI: http://localhost:8000/docs
- Startup logs print the active generator: `openai` (DashScope/Qwen and other compatible endpoints) / `claude` / `mock`
- If `LLM_PROVIDER` is set but its API key is missing → automatic fallback to `mock`, endpoints keep working

## LLM provider

| provider | required env vars | notes |
|---|---|---|
| `openai` | `DASHSCOPE_API_KEY` (or `OPENAI_API_KEY`) + base URL + `OPENAI_MODEL` | OpenAI-compatible, defaults to DashScope `qwen3-max` |
| `claude` | `ANTHROPIC_API_KEY` + `LLM_MODEL` | Anthropic, forced single tool call |
| `mock` | none | deterministic fake data, for wiring things up |

## Auth

Single-user login gate. Every endpoint except `/api/health` and `/api/auth/*` requires `Authorization: Bearer <token>`.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/auth/status` | `{registered}` — the frontend shows login vs register based on this |
| POST | `/api/auth/register` | `{email, password}` → token; **only open while there are 0 users** |
| POST | `/api/auth/login` | `{email, password}` → token |
| GET | `/api/auth/me` | validate + sliding-renew the token |

The token is an HS256 JWT signed with `AUTH_SECRET`, valid for `AUTH_TOKEN_TTL_HOURS` (default 720h); passwords are bcrypt-hashed.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | LLM provider + model (no auth) |
| GET | `/api/decks` | deck list + per-deck counts: `card_count`, `new_count` (never studied), `learn_count` (learning/relearning due now), `due_count` (review-state due now) |
| POST | `/api/decks` | `{name, language?}` create a deck |
| PATCH | `/api/decks/{id}` | rename (default decks can't be renamed) |
| DELETE | `/api/decks/{id}?keep_cards=` | delete the deck **and its cards + review history** (Anki-style); `keep_cards=true` instead moves the cards to the default deck. Default decks can't be deleted |
| POST | `/api/generate-card` | `{word, language, context?, deck_id?, use_query_as_prompt?}` → LLM resolves the query to a target-language headword + English card, persists it (no `deck_id` = `new-<lang>`) |
| POST | `/api/cards` | `{deck_id?, language, word, prompt?, translation?, definitions?, examples?, ...}` → **manual** card, no LLM (`source="manual"`); 409 if the word already exists |
| GET | `/api/words?language=&deck_id=&q=&offset=&limit=` | card library (pagination + search + deck filter) |
| GET `/` PATCH `/` DELETE | `/api/cards/{id}` | view / edit (can change `deck_id`, `source`→`manual`) / delete |
| GET | `/api/review/due?language=&deck_id=&limit=` | today's due queue |
| POST | `/api/review/submit` | `{word_id, rating:1-4}` → FSRS update + write `review_logs` |
| GET | `/api/review/stats` | total / new / learn (due now) / due (review, due now) / reviewed today / by language |
| GET | `/api/review/heatmap?days=&tz_offset_minutes=` | GitHub-style activity: reviews+added per day, current/longest/total streak |
| POST | `/api/import/anki/preview` | multipart `.apkg` upload → note types, fields, decks, sample notes, `import_id` (kept in memory 30 min) |
| POST | `/api/import/anki/commit` | `{import_id, deck_name, language, note_type, word_field, word_extract, prompt_field?, meaning_field?, examples_field?, import_progress, on_duplicate}` → creates the deck + Word cards; `on_duplicate` = `skip` \| `overwrite`. Response has `imported` / `updated` / `skipped` |
| POST | `/api/cards/{word_id}/recordings` | multipart audio blob → saves it as a `user_recording` MediaFile on the word |
| POST | `/api/cards/{word_id}/media` | multipart image / audio / video file → attaches it (`kind` derived from MIME, `source="upload"`) |
| GET | `/api/media/{media_id}` | streams the media file (range requests supported → video seeking) |
| DELETE | `/api/media/{media_id}` | deletes the file + row |

## Layout

```
app/
├── main.py              FastAPI app + CORS + lifespan (create tables / migrate / seed default decks)
├── config.py            pydantic-settings; falls back to mock when a provider has no key
├── auth.py              bcrypt passwords + JWT + get_current_user dependency
├── anki_import.py       parse an .apkg (zip → SQLite + media, incl. zstd anki21b / v3 protobuf) into plain structures
├── media_store.py       audio/other files on disk under settings.media_dir
├── time_utils.py        naive UTC everywhere (avoids the SQLite due<=now comparison trap)
├── db.py                engine / session / init_db + lightweight migration (ALTER words ADD deck_id) + default decks
├── models.py            User / Deck / Word / FsrsCard / ReviewLog / MediaFile
├── schemas.py           request/response DTOs + LLMCard (structured-output schema)
├── llm/
│   ├── base.py          CardGenerator protocol
│   ├── openai_compat.py OpenAI-compatible (DashScope/Qwen…), JSON-mode output
│   ├── claude.py        Anthropic: forced single save_vocab_card tool call
│   └── mock.py          deterministic fake data, incl. a German-article heuristic
├── services/
│   ├── cards.py         lookup orchestration + card CRUD (update/delete/pagination/decks)
│   ├── decks.py         deck CRUD + resolve_deck + get_or_create_default
│   ├── review.py        due_queue / submit / stats / heatmap
│   ├── media.py         list media per word / add recording / serve / delete
│   ├── anki_import.py   in-memory stash of a parsed .apkg + commit (deck + Word + FSRS approx + audio)
│   └── fsrs.py          py-fsrs wrapper (new_card / review)
└── routers/
    ├── auth.py          /api/auth/*
    ├── decks.py         /api/decks/*
    ├── cards.py         /api/generate-card, /api/words, /api/cards/*, /api/cards/{id}/recordings
    ├── review.py        /api/review/*
    ├── media.py         /api/media/*
    └── import_.py       /api/import/anki/*
```

## Notes

- **Registration is only open while there are 0 users** (single-user gate). To switch accounts: delete `language_learning.db` and restart.
- Default decks `new-en` / `new-de` are seeded in `init_db`. Deleting a custom deck deletes its cards + review history by default (Anki-style); pass `keep_cards=true` to move them to the default deck instead.
- An existing older DB gets `words.deck_id` added automatically and deckless cards assigned to the default deck (`db.py::_migrate` + `_seed_decks`).
- `(word, language)` is unique. Looking up the same word again **updates** the card instead of creating a new one; the `created` field reflects which happened.
- `fsrs_cards.card_json` holds the full py-fsrs `Card.to_dict()` state — the source of truth for algorithm state; the mirror columns exist for querying.
- rating map: 1=Again 2=Hard 3=Good 4=Easy; `reps` / `lapses` are maintained by the service (py-fsrs v5 Card doesn't track them).
- The heatmap groups by the user's local date using `tz_offset_minutes` (the frontend sends `-getTimezoneOffset()`).
- `Word.word` is always the target-language headword — YouGlish search, German gender, and the `(word, language)` uniqueness key all use it. `Word.prompt` is an optional custom review-front text (e.g. a native-language prompt); review shows `prompt or word`, YouGlish always uses `word`.
- **Cross-language lookup**: the search text can be Chinese, an English synonym (when target is German), or an inflected/misspelled form. The LLM resolves it to the canonical headword (`die Sorge` from "担心" + `de`; `laufen` from "gelaufen"), writes all explanations in **English**, and sets `query_language`. When the query wasn't the target language and `use_query_as_prompt` is true, the raw query is stored as `Word.prompt`. Dedup is on the resolved headword, so "担心" then "Sorge" (both `de`) update the same card.
- Anki import maps one note → one Word. `word_extract` can take the whole field or the part before a `– : ,` separator (for decks where the word sits inside a "Wort – meaning" field). `prompt_field` fills `Word.prompt` — so a Chinese-front / German-back Anki deck imports as prompt=Chinese, word=German. It does **not** extract gender/plural. FSRS progress is approximated: Anki `ivl` → stability, `factor` → difficulty, review/learning state carried over; the **actual due date** is reconstructed from Anki's `card.due` + `col.crt` (review cards store `due` as days-since-collection-creation), so cards that were overdue in Anki come in overdue here. "new" cards start as `new`. `source` is set to `anki_import`.
- **Progress only survives if the `.apkg` was exported with "Include scheduling information" checked** — otherwise Anki strips `type`/`ivl`/`revlog` on export and every card imports as New. The preview response's `notes_with_progress` reports how many notes carry scheduling data; the UI warns when it's 0.
- **Audio**: `[sound:x.mp3]` refs in mapped fields are extracted to `MediaFile` rows + files under `settings.media_dir` (handles the v3 package: zstd-decompressing both the protobuf `media` manifest and each numbered media file). `word_field` audio → `kind="word"`, `examples_field` → `"example"`, `meaning_field`/`prompt_field` → `"extra"`. `on_duplicate="overwrite"` replaces a word's `anki_import` media. Playback is a blob fetched with the auth token → native `<audio controls>`. User recordings (`MediaRecorder` in the browser) POST to `/api/cards/{id}/recordings` and store as `kind="user_recording"`.
