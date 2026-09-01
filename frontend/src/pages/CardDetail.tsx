import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import CardView from "../components/CardView";
import EditCardForm from "../components/EditCardForm";
import { api } from "../api";
import type { GenerateCardResponse, WordUpdate } from "../types";

export default function CardDetail() {
  const { id } = useParams();
  const wordId = Number(id);
  const navigate = useNavigate();

  const [data, setData] = useState<GenerateCardResponse | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    setError(null);
    api.getCard(wordId).then(setData).catch((e) => setError(String(e)));
  }
  useEffect(load, [wordId]);

  async function save(patch: WordUpdate) {
    setBusy(true);
    setError(null);
    try {
      setData(await api.updateCard(wordId, patch));
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this card? Its review history is deleted too.")) return;
    setBusy(true);
    try {
      await api.deleteCard(wordId);
      navigate("/cards");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  if (error && !data) return <main className="page"><div className="error">{error}</div></main>;
  if (!data) return <main className="page"><p className="muted">Loading…</p></main>;

  return (
    <main className="page">
      <p className="muted">
        <Link to="/cards">← Cards</Link>
      </p>
      {error && <div className="error">{error}</div>}

      {editing ? (
        <EditCardForm data={data} busy={busy} onCancel={() => setEditing(false)} onSave={save} />
      ) : (
        <>
          <div className="detail-actions">
            <button onClick={() => setEditing(true)}>Edit</button>
            <button className="danger" disabled={busy} onClick={remove}>
              Delete
            </button>
          </div>
          <CardView data={data} />
        </>
      )}
    </main>
  );
}
