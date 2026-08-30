# Lingua Loop

A personal English / German study workflow — replaces the scattered Anki + YouGlish + manual-notes routine.

- Requirements & architecture decisions: [`PROJECT_SPEC.md`](./PROJECT_SPEC.md)
- Technical architecture: [`ARCHITECTURE.md`](./ARCHITECTURE.md)

## Current state

A basic card review system (Anki / Quizlet style) is running:

- **Login gate** — email + password, single user (registration is only open while no account exists)
- **Decks** — Anki-style. `new-en` / `new-de` are created automatically; pick a deck or create one on the fly when looking up a word
- **Look up → LLM structured card → self-hosted FSRS store** — or **add a card by hand** (no AI, Anki-style, with drag/drop/paste image·audio·video attachments)
- **Review** — today's due queue (filterable by deck) + reveal answer + Again/Hard/Good/Easy grading (keys 1–4 / Space) + FSRS state update
- **Card library** — paginated list + search + language / deck filters
- **Card detail** — view / edit (incl. moving decks) / delete
- **YouGlish** — expandable real-pronunciation clips from YouTube (official widget, next/previous, EN/DE auto-routed)
- **Anki import** — upload an `.apkg`, map its fields, and it creates a deck (review progress approximated from the Anki interval/ease; audio `[sound:]` clips imported too)
- **Audio** — play imported pronunciation clips on a card, and record your own takes (mic) for shadowing practice
- **Dashboard** — due / new / reviewed today / total + a GitHub-style study-activity heatmap (current / longest / total streak) + per-deck entry points

```
backend/   FastAPI + SQLModel/SQLite + py-fsrs + LLM (DashScope-Qwen / Claude / mock)
frontend/  Vite + React + TS + react-router
```

## Quick start

```bash
# 1. Backend (terminal A)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000     # → http://localhost:8000/docs
#   .env is preconfigured for DashScope (qwen3-max); to switch provider see backend/.env.example

# 2. Frontend (terminal B)
cd frontend
npm install
npm run dev                                            # → http://localhost:5173
```

On first visit to http://localhost:5173 you **register** (email + password). Registration then closes; after that it's login only.
To switch accounts / start over: delete `backend/language_learning.db` and restart.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Look up → LLM card → FSRS store | ✅ |
| 2 | Review UI + card CRUD + card library + routing | ✅ |
| 3 | YouGlish widget embedded in cards | ✅ |
| + | Login gate + decks + study-activity heatmap + Anki `.apkg` import | ✅ |
| 4 | Conversation practice (tool calls: recent words / mark produced) | ⬜ |
| 5 | Nicos Weg workflow (dictation diff agent) | ⬜ |

