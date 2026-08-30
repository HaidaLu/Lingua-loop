# Architecture — Lingua Loop

> Companion to `PROJECT_SPEC.md`. This file records the **decoupled frontend/backend** technical architecture and what has shipped.

---

## 1. Overall architecture

```
┌─────────────────────────┐         HTTP / JSON          ┌──────────────────────────────┐
│  Frontend (Vite+React)  │  ───────────────────────▶   │   Backend (FastAPI)          │
│  localhost:5173         │  ◀───────────────────────   │   localhost:8000             │
│                         │                              │                              │
│  Dashboard / Review /   │                              │  /api/auth/*                 │
│  Look up / Cards /      │                              │  /api/decks/*                │
│  Decks (react-router)   │                              │  /api/generate-card          │
└─────────────────────────┘                              │  /api/words  /api/cards/{id} │
                                                         │  /api/review/{due,submit,    │
                                                         │              stats,heatmap}  │
                                                         │  /api/health                 │
                                                         │  ┌────────────────────────┐  │
                                                         │  │ LLM layer (pluggable)  │  │
                                                         │  │  - openai (Qwen/compat)│  │
                                                         │  │  - claude (Anthropic)  │  │
                                                         │  │  - mock   (no key)     │  │
                                                         │  └────────────────────────┘  │
                                                         │  ┌────────────────────────┐  │
                                                         │  │ FSRS service (py-fsrs) │  │
                                                         │  └────────────────────────┘  │
                                                         │  ┌────────────────────────┐  │
                                                         │  │ SQLite (SQLModel ORM)  │  │
                                                         │  └────────────────────────┘  │
                                                         └──────────────────────────────┘
```

**Why decoupled frontend/backend** (overriding the SPEC's lean toward an all-in-one Next.js app):
- The backend is Python — reuses experience from the RAG project; `py-fsrs` is the reference implementation, closer to the algorithm authors than `ts-fsrs`.
- The frontend is fully static — later the backend can go on a VPS and the frontend on Vercel / static hosting, independently.
- LLM orchestration, agents (the Nicos Weg workflow), Whisper, etc. all fit the Python ecosystem better.

---

## 2. Backend layering

| Layer | Directory | Responsibility |
|---|---|---|
| API routers | `app/routers/` | validate input, call a service, assemble the response |
| Service | `app/services/` | orchestration: `cards.py` (lookup→LLM→persist + card CRUD), `decks.py` (deck CRUD), `review.py` (queue/grade/stats/heatmap), `fsrs.py` (FSRS wrapper) |
| LLM adapter | `app/llm/` | `base.py` defines the `CardGenerator` protocol; `openai_compat.py` / `claude.py` / `mock.py` are the three implementations, switched by `LLM_PROVIDER` |
| Data model | `app/models.py` | SQLModel tables: `User` / `Deck` / `Word` / `FsrsCard` / `ReviewLog` |
| Schema | `app/schemas.py` | request/response DTOs + the LLM structured-output schema |
| Infra | `app/config.py` `app/db.py` `app/auth.py` `app/time_utils.py` | settings (pydantic-settings), DB engine/session, auth, naive-UTC time |

**Pluggable LLM**: `get_generator()` returns an implementation based on config.
- `openai` (current default) → OpenAI-compatible endpoints incl. DashScope/Qwen and OpenAI. Uses JSON mode (`response_format={"type":"json_object"}`, falls back to prompt-only), then Pydantic-validates.
- `claude` → Anthropic, forced single `save_vocab_card` tool call for structured JSON (SDK-version agnostic).
- If the chosen provider has no key → automatic fallback to `mock` (with a warning) so endpoints always work.

**Time is naive UTC everywhere**: SQLite drops tzinfo, so mixing aware/naive in `due_date <= now()` breaks comparisons — `time_utils.utcnow()` always returns naive UTC.

---

## 3. Data model

Aligned with SPEC §4 (conversation / Nicos Weg tables come later):

- **`users`** — single-user gate. `email` unique, `password_hash` (bcrypt). Registration is only open while there are 0 users.
- **`decks`** — a deck. `name` unique, `language` (`en`/`de`/null), `is_default`. `new-en` / `new-de` are seeded in `init_db`.
- **`words`** — the vocabulary entry. `word` is always the target-language headword (YouGlish / gender / uniqueness key). `prompt` (optional) is a custom review-front text — review shows `prompt or word`, YouGlish still uses `word`. `deck_id` → `decks`. German-only fields `gender` / `plural_form` / `case_notes`. `source` (`llm_lookup` / `manual` / `anki_import`).
- **`fsrs_cards`** — one review state per word. `state` / `stability` / `difficulty` / `due_date` / `reps` / `lapses` / `last_review` + `card_json` (full py-fsrs `Card.to_dict()` serialization, the source of truth, losslessly reconstructable).
- **`review_logs`** — one row per grade (rating 1-4 + `reviewed_at`). The heatmap aggregates from here + `words.created_at`.

Unique constraint: `(word, language)` — looking up the same word again updates rather than creating a duplicate.

**Migration**: `db.py::_migrate()` idempotently adds `deck_id` to an existing `words` table (SQLModel `create_all` won't ALTER), and `_seed_decks()` seeds the default decks and backfills orphan cards.

**Auth**: every router except `/api/health` and `/api/auth/*` mounts `Depends(get_current_user)`; HS256 JWT (`AUTH_SECRET`), `Bearer` header.

**Anki import** (`app/anki_import.py` + `app/services/anki_import.py`): an `.apkg` is a zip holding a SQLite collection (`collection.anki2` / `.anki21`, or zstd-compressed `.anki21b`). The parser handles both the old JSON `col.models`/`col.decks` schema and the newer `notetypes`/`fields`/`decks` tables, strips HTML/cloze/`[sound:]` from fields, and takes the most-progressed card per note for scheduling. `preview` stashes the parsed package in memory (30-min TTL); `commit` maps the chosen fields → `Word` rows in a new deck, `source="anki_import"`, and approximates FSRS state from Anki `ivl`→stability / `factor`→difficulty (or `new` for unstudied cards). `word_extract` can trim the word to the part before a `– : ,` separator; `prompt_field` fills `Word.prompt` (so a Chinese-front deck imports as prompt=Chinese / word=German). It does not extract German gender.

---

## 4. Core flow: look up → LLM card → FSRS store

```
POST /api/generate-card  { word, language: "en"|"de", context?, deck_id? }
        │
        ▼
services.cards.generate_card()
        │  1. resolve the deck (explicit deck_id, else the default deck for the language)
        │  2. LLM resolves the query -> canonical headword (target language) + English card + query_language
        │  3. word = headword; if the query was another language -> keep it as Word.prompt
        │  4. upsert Word (by headword + language); apply the English fields
        │  5. if no FsrsCard → services.fsrs.new_card() init (state="new"), persist
        │  6. commit
        ▼
returns  { word: {...all fields}, fsrs: { state, due_date, ... }, llm_provider, created }

The card generator's system prompt does three things: resolve any-language input to the target-language
headword, keep all explanations in English (the user can't yet read German definitions), and flag whether
the input was cross-language. YouGlish then searches `Word.word` (the headword) regardless of what was typed.
```

---

## 5. Frontend (React + react-router)

`AuthProvider` (`src/auth.tsx`) manages the token (localStorage `ll_token`). Not signed in → `Login`; signed in → the App layout (top nav + provider badge + sign out) + routed pages:

| Route | Page | APIs used |
|---|---|---|
| — | `Login` — email+password, toggles login/register by `/api/auth/status` | `POST /api/auth/{register,login}` |
| `/` | `Dashboard` — stats + **GitHub-style heatmap** (`Heatmap.tsx`, current/longest/total streak) + per-deck entry points | `stats` / `heatmap` / `decks` |
| `/review` | `ReviewSession` — one card at a time: show word → reveal → grade 1-4 (Space / 1-4); `?deck_id=` filters by deck | `review/due` `review/submit` |
| `/lookup` | `Lookup` — lookup form (deck picker + create-on-the-fly) + the generated card | `generate-card` `decks` |
| `/cards` | `CardList` — paginated table + search + language / deck filters | `words` `decks` |
| `/cards/:id` | `CardDetail` — view / edit (incl. deck, array fields edited line-by-line) / delete | `cards/{id}` `decks` |
| `/cards/new` | `AddCard` — Anki-style manual card form (no LLM) + drop/browse/paste image·audio·video, "keep adding" flow | `POST /api/cards`, `POST /api/cards/{id}/media` |
| `/decks` | `Decks` — deck list + create / rename / delete + link to import | `decks/*` |
| `/import/anki` | `ImportAnki` — upload `.apkg` → preview + field mapping → commit | `import/anki/{preview,commit}` |

`api.ts` reads the token from localStorage and attaches the `Authorization` header; a 401 on a non-auth endpoint triggers a global sign-out.
In dev the vite proxy forwards `/api` to the backend on 8000.

**YouGlish integration** (`src/youglish.ts` + `src/components/YouglishWidget.tsx`):
- Loads the official `https://youglish.com/public/emb/widget.js`, using a global `onYouglishAPIReady` callback + a module-level Promise cache so it loads once.
- `CardView` has a collapsible section (collapsed by default, to avoid autoplay + save the anonymous quota); expanding it does `new YG.Widget(id, {components:14})` then `widget.fetch(word, "english"|"german")`.
- On word change it reuses the instance and re-`fetch`es; the built-in next/previous buttons call `widget.next()/previous()`; `onFetchDone` fills in the clip count.
- Keeps the official "powered by YouGlish.com" mark (built into the widget) + an extra source credit. Personal use only; anonymous calls have a daily quota.
- **Not a static iframe** — the widget API natively supports switching to the next clip.

---

## 6. Roadmap (aligned with SPEC §6)

| Phase | Scope | Status |
|---|---|---|
| **1** | Look up → LLM card → self-hosted FSRS store | ✅ |
| **2** | Review UI (due queue + grading + FSRS update) + card CRUD + card library + routing | ✅ |
| **3** | YouGlish widget embedded in cards (EN/DE, collapsible, next clip) | ✅ |
| **+** | Login gate (single user, email+password) + decks + study-activity heatmap + Anki `.apkg` import | ✅ |
| 4 | Conversation practice (`get_recent_words` / `mark_word_used` tool calls) | planned |
| 5 | Nicos Weg workflow (dictation diff agent) | planned |

---

## 7. Running

```bash
# backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000   # .env is preconfigured for DashScope/Qwen
# Swagger: http://localhost:8000/docs

# frontend
cd frontend
npm install
npm run dev                                          # http://localhost:5173
```

To switch LLM provider (Claude / official OpenAI / mock): edit `backend/.env`, see `backend/.env.example`.
