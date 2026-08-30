import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import type { DeckOut, Language, WordListResponse } from "../types";

const PAGE = 25;

export default function CardList() {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<WordListResponse | null>(null);
  const [decks, setDecks] = useState<DeckOut[]>([]);
  const [lang, setLang] = useState<"" | Language>("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const deckId = params.get("deck_id") ? Number(params.get("deck_id")) : undefined;

  useEffect(() => {
    api.listDecks().then(setDecks).catch(() => {});
  }, []);

  useEffect(() => {
    setError(null);
    api
      .listWords({
        language: lang || undefined,
        deck_id: deckId,
        q: q.trim() || undefined,
        offset,
        limit: PAGE,
      })
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [lang, q, offset, deckId]);

  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE));
  const page = Math.floor(offset / PAGE) + 1;

  function setDeck(v: string) {
    setOffset(0);
    const next = new URLSearchParams(params);
    if (v) next.set("deck_id", v);
    else next.delete("deck_id");
    setParams(next);
  }

  return (
    <main className="page">
      <div className="hm-head">
        <h1>Cards{data ? ` (${total})` : ""}</h1>
        <Link
          className="btn primary"
          to={`/cards/new${deckId ? `?deck_id=${deckId}` : ""}`}
        >
          + Add card
        </Link>
      </div>

      <div className="filters">
        <input
          placeholder="Search words…"
          value={q}
          onChange={(e) => {
            setOffset(0);
            setQ(e.target.value);
          }}
        />
        <select
          value={lang}
          onChange={(e) => {
            setOffset(0);
            setLang(e.target.value as "" | Language);
          }}
        >
          <option value="">All languages</option>
          <option value="en">English</option>
          <option value="de">German</option>
        </select>
        <select value={deckId ?? ""} onChange={(e) => setDeck(e.target.value)}>
          <option value="">All decks</option>
          {decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="error">{error}</div>}

      <table className="card-table">
        <thead>
          <tr>
            <th>Word</th>
            <th>Meaning</th>
            <th>Deck</th>
            <th>Lang</th>
          </tr>
        </thead>
        <tbody>
          {data?.items.map((w) => (
            <tr key={w.id}>
              <td>
                <Link to={`/cards/${w.id}`}>
                  {w.gender ? `${w.gender} ` : ""}
                  {w.word}
                </Link>
              </td>
              <td className="ellipsis">{w.translation || w.definitions[0] || "—"}</td>
              <td className="muted">{w.deck_name ?? "—"}</td>
              <td>{w.language.toUpperCase()}</td>
            </tr>
          ))}
          {data && data.items.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                No cards yet. <Link to="/lookup">Look up a word</Link> to create one.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {pageCount > 1 && (
        <div className="pager">
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            Previous
          </button>
          <span>
            {page} / {pageCount}
          </span>
          <button disabled={page >= pageCount} onClick={() => setOffset(offset + PAGE)}>
            Next
          </button>
        </div>
      )}
    </main>
  );
}
