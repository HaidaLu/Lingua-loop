import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import CardView from "../components/CardView";
import EditCardForm from "../components/EditCardForm";
import { api } from "../api";
import type { GenerateCardResponse, Rating, ReviewItem, WordUpdate } from "../types";

const RATINGS: { rating: Rating; label: string; hint: string; cls: string }[] = [
  { rating: 1, label: "Again", hint: "no recall", cls: "again" },
  { rating: 2, label: "Hard", hint: "recalled with effort", cls: "hard" },
  { rating: 3, label: "Good", hint: "recalled normally", cls: "good" },
  { rating: 4, label: "Easy", hint: "instant", cls: "easy" },
];

export default function ReviewSession() {
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [editing, setEditing] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [params] = useSearchParams();
  const deckId = params.get("deck_id") ? Number(params.get("deck_id")) : undefined;

  useEffect(() => {
    api
      .due({ limit: 100, deck_id: deckId })
      .then((r) => setQueue(r.items))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [deckId]);

  const current = queue[idx];

  const grade = useCallback(
    async (rating: Rating) => {
      if (!current || submitting) return;
      setSubmitting(true);
      try {
        await api.submitReview(current.word.id, rating);
        setDone((d) => d + 1);
        setRevealed(false);
        setEditing(false);
        setIdx((i) => i + 1);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setSubmitting(false);
      }
    },
    [current, submitting],
  );

  const saveEdit = useCallback(
    async (patch: WordUpdate) => {
      if (!current) return;
      setSavingEdit(true);
      setEditError(null);
      try {
        const updated = await api.updateCard(current.word.id, patch);
        setQueue((q) =>
          q.map((it, i) =>
            i === idx ? { ...it, word: updated.word, fsrs: updated.fsrs } : it,
          ),
        );
        setEditing(false);
      } catch (e) {
        setEditError(e instanceof Error ? e.message : String(e));
      } finally {
        setSavingEdit(false);
      }
    },
    [current, idx],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!current || editing) return;
      if (!revealed && (e.key === " " || e.key === "Enter")) {
        e.preventDefault();
        setRevealed(true);
      } else if (revealed && ["1", "2", "3", "4"].includes(e.key)) {
        grade(Number(e.key) as Rating);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, revealed, editing, grade]);

  if (loading) return <main className="page"><p className="muted">Loading review queue…</p></main>;
  if (error) return <main className="page"><div className="error">{error}</div></main>;

  if (!current) {
    return (
      <main className="page review-done">
        <h1>{done > 0 ? "Review complete 🎉" : "Nothing due today"}</h1>
        <p className="muted">Reviewed {done} card{done === 1 ? "" : "s"} this session.</p>
        <div className="cta-row">
          <Link className="btn" to="/">Back to dashboard</Link>
          <Link className="btn" to="/lookup">Look up new words</Link>
        </div>
      </main>
    );
  }

  const w = current.word;
  const fakeCard: GenerateCardResponse = {
    word: w,
    fsrs: current.fsrs,
    llm_provider: "-",
    created: false,
  };

  return (
    <main className="page review">
      <div className="review-progress">
        {idx + 1} / {queue.length} · {done} done
      </div>

      {!revealed ? (
        <div className="review-front" onClick={() => setRevealed(true)}>
          <div className="front-word">{w.prompt || w.word}</div>
          <div className="muted">
            {w.prompt ? "recall the word" : w.language.toUpperCase()} · click or press Space to reveal
          </div>
        </div>
      ) : editing ? (
        <>
          {editError && <div className="error">{editError}</div>}
          <EditCardForm
            data={fakeCard}
            busy={savingEdit}
            onCancel={() => {
              setEditError(null);
              setEditing(false);
            }}
            onSave={saveEdit}
          />
        </>
      ) : (
        <>
          <div className="detail-actions">
            <button
              onClick={() => {
                setEditError(null);
                setEditing(true);
              }}
            >
              Edit card
            </button>
          </div>
          <CardView data={fakeCard} />
          <div className="rating-row">
            {RATINGS.map((r) => (
              <button
                key={r.rating}
                className={`rating ${r.cls}`}
                disabled={submitting}
                onClick={() => grade(r.rating)}
              >
                <span className="rating-key">{r.rating}</span>
                {r.label}
                <span className="rating-hint">{r.hint}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
