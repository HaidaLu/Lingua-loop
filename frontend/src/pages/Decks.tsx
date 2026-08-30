import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { DeckOut, Language } from "../types";

export default function Decks() {
  const [decks, setDecks] = useState<DeckOut[]>([]);
  const [name, setName] = useState("");
  const [lang, setLang] = useState<"" | Language>("");
  const [error, setError] = useState<string | null>(null);

  const load = () => api.listDecks().then(setDecks).catch((e) => setError(String(e)));
  useEffect(() => {
    load();
  }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.createDeck(name.trim(), lang || undefined);
      setName("");
      setLang("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function rename(d: DeckOut) {
    const next = prompt("New name", d.name);
    if (!next || next === d.name) return;
    try {
      await api.renameDeck(d.id, next.trim());
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function remove(d: DeckOut) {
    const n = d.card_count;
    if (n > 0) {
      const keep = confirm(
        `Delete deck “${d.name}” AND its ${n} card${n === 1 ? "" : "s"} (incl. review history)?\n\n` +
          `OK = delete everything.\nCancel = keep the deck.`,
      );
      if (!keep) return;
    } else if (!confirm(`Delete empty deck “${d.name}”?`)) {
      return;
    }
    try {
      await api.deleteDeck(d.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <main className="page">
      <div className="hm-head">
        <h1>Decks</h1>
        <Link className="muted" to="/import/anki">
          Import from Anki →
        </Link>
      </div>
      {error && <div className="error">{error}</div>}

      <form className="deck-new" onSubmit={create}>
        <input
          placeholder="New deck name, e.g. B1-Wortschatz"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <select value={lang} onChange={(e) => setLang(e.target.value as "" | Language)}>
          <option value="">Any language</option>
          <option value="en">English</option>
          <option value="de">German</option>
        </select>
        <button className="primary" type="submit">
          Create deck
        </button>
      </form>

      <table className="card-table">
        <thead>
          <tr>
            <th>Deck</th>
            <th>Lang</th>
            <th>Cards</th>
            <th className="col-new">New</th>
            <th className="col-learn">Learn</th>
            <th className="col-due">Due</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {decks.map((d) => (
            <tr key={d.id}>
              <td>
                <Link to={`/cards?deck_id=${d.id}`}>{d.name}</Link>
                {d.is_default && <span className="badge" style={{ marginLeft: 6 }}>default</span>}
              </td>
              <td>{d.language ? d.language.toUpperCase() : "—"}</td>
              <td>{d.card_count}</td>
              <td className="col-new">{d.new_count || 0}</td>
              <td className="col-learn">{d.learn_count || 0}</td>
              <td className="col-due">{d.due_count || 0}</td>
              <td className="row-actions">
                <Link to={`/cards/new?deck_id=${d.id}`}>+ Add</Link>
                <Link to={`/review?deck_id=${d.id}`}>Review</Link>
                {!d.is_default && (
                  <>
                    <button onClick={() => rename(d)}>Rename</button>
                    <button className="danger" onClick={() => remove(d)}>
                      Delete
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">
        The default decks new-en / new-de are created automatically on your first lookup and can’t be
        renamed or deleted.
      </p>
    </main>
  );
}
