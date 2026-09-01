import { useEffect, useRef, useState } from "react";
import type { Language } from "../types";
import { api } from "../api";
import {
  loadYouglish,
  sanitizeYouglishQuery,
  youglishTermFor,
  ygLangName,
  type YGWidget,
} from "../youglish";

// components: 2 caption + 4 video info + 8 controls = 14 (no search box; query comes from the card)
const COMPONENTS = 14;
const FETCH_TIMEOUT_MS = 15000;

export default function YouglishWidget({
  word,
  language,
  wordId,
  storedTerm,
}: {
  word: string;
  language: Language;
  wordId?: number;
  storedTerm?: string | null;
}) {
  const idRef = useRef("yg-" + Math.random().toString(36).slice(2, 10));
  const widgetRef = useRef<YGWidget | null>(null);
  const createdRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState<number | null>(null);

  // 1. figure out what to actually search on YouGlish
  const [query, setQuery] = useState<string | null>(() => {
    if (storedTerm && storedTerm.trim()) return youglishTermFor(storedTerm, language);
    const local = sanitizeYouglishQuery(word, language);
    return local || (wordId ? null : ""); // null => ask the backend; "" => nothing usable
  });
  const [resolving, setResolving] = useState(query === null);

  useEffect(() => {
    if (query !== null || !wordId) return;
    let cancelled = false;
    setResolving(true);
    api
      .youglishTerm(wordId)
      .then((r) => {
        if (!cancelled)
          setQuery(sanitizeYouglishQuery(r.term, language) || youglishTermFor(r.term, language) || "");
      })
      .catch(() => {
        if (!cancelled) setQuery(sanitizeYouglishQuery(word, language) || "");
      })
      .finally(() => {
        if (!cancelled) setResolving(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, wordId, word]);

  // 2. create the widget instance once we have a usable query
  useEffect(() => {
    if (!query) return;
    let cancelled = false;
    let timer = 0;
    const clearTimer = () => window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      if (!cancelled) {
        setCount((c) => c ?? 0);
        setError((e) =>
          e ?? "YouGlish didn't respond (the query may be unsupported or the daily quota is used up).",
        );
      }
    }, FETCH_TIMEOUT_MS);

    loadYouglish()
      .then((YG) => {
        if (cancelled) return;
        if (!createdRef.current) {
          createdRef.current = true;
          widgetRef.current = new YG.Widget(idRef.current, {
            width: 640,
            components: COMPONENTS,
            events: {
              onFetchDone: (e) => {
                clearTimer();
                setCount((e as { totalResult?: number }).totalResult ?? 0);
              },
              onError: () => {
                clearTimer();
                setError("YouGlish error (the anonymous daily quota may be used up)");
              },
              onWidgetError: () => {
                clearTimer();
                setError("YouGlish error (the anonymous daily quota may be used up)");
              },
            },
          });
        }
        widgetRef.current?.fetch(query, ygLangName(language));
      })
      .catch((e: Error) => {
        clearTimer();
        setError(e.message);
      });

    const id = idRef.current;
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      const el = document.getElementById(id);
      if (el) el.innerHTML = "";
      widgetRef.current = null;
      createdRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, language]);

  if (resolving) {
    return (
      <div className="yg">
        <p className="muted">Working out which word to look up…</p>
      </div>
    );
  }

  if (query === "") {
    return (
      <div className="yg">
        <p className="muted">
          Couldn't turn this card into a single word to search on YouGlish. Edit the card's word to a
          plain headword and try again.
        </p>
      </div>
    );
  }

  return (
    <div className="yg">
      {error ? (
        <p className="muted">{error}</p>
      ) : (
        <>
          <p className="muted yg-query">Clips for “{query}”</p>
          <div id={idRef.current} className="yg-slot" />
          <div className="yg-bar">
            <button type="button" onClick={() => widgetRef.current?.previous?.()}>
              ← Previous
            </button>
            <button type="button" onClick={() => widgetRef.current?.next()}>
              Next →
            </button>
            <span className="muted">
              {count == null
                ? "Loading…"
                : count === 0
                  ? "No clips found"
                  : `${count} YouTube clips`}
            </span>
          </div>
        </>
      )}
      <p className="yg-credit">
        Clips from <a href="https://youglish.com" target="_blank" rel="noreferrer">YouGlish.com</a>
      </p>
    </div>
  );
}
