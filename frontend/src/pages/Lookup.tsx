import { useState } from "react";
import { Link } from "react-router-dom";
import LookupForm from "../components/LookupForm";
import CardView from "../components/CardView";
import { api } from "../api";
import type { GenerateCardResponse, Language } from "../types";

export default function Lookup() {
  const [card, setCard] = useState<GenerateCardResponse | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLookup(input: {
    word: string;
    language: Language;
    context?: string;
    deck_id?: number;
    use_query_as_prompt?: boolean;
  }) {
    setLoading(true);
    setError(null);
    setQuery(input.word);
    try {
      setCard(await api.generateCard(input));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const resolved =
    card && query && query.trim().toLowerCase() !== card.word.word.toLowerCase();

  return (
    <main className="page">
      <h1>Look up → generate card</h1>
      <LookupForm loading={loading} onSubmit={handleLookup} />
      {error && <div className="error">Error: {error}</div>}
      {card ? (
        <>
          <p className="muted">
            {resolved && (
              <>
                “{query}” → <b>{card.word.word}</b> ·{" "}
              </>
            )}
            {card.created ? "Card created" : "Word already existed — card content updated"}
            {card.word.deck_name && ` → deck “${card.word.deck_name}”`} ·{" "}
            <Link to={`/cards/${card.word.id}`}>open card</Link>
          </p>
          <CardView data={card} />
        </>
      ) : (
        <p className="muted">
          Look up a word — or type its meaning in any language and the target word is resolved for you.
        </p>
      )}
    </main>
  );
}
