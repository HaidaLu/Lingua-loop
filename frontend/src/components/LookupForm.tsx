import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { DeckOut, Language } from "../types";

export default function LookupForm({
  loading,
  onSubmit,
}: {
  loading: boolean;
  onSubmit: (input: {
    word: string;
    language: Language;
    context?: string;
    deck_id?: number;
    use_query_as_prompt?: boolean;
  }) => void;
}) {
  const [word, setWord] = useState("");
  const [language, setLanguage] = useState<Language>("en");
  const [context, setContext] = useState("");
  const [deckId, setDeckId] = useState<string>(""); // "" = default deck
  const [keepPrompt, setKeepPrompt] = useState(true);
  const [decks, setDecks] = useState<DeckOut[]>([]);

  function reloadDecks() {
    api.listDecks().then(setDecks).catch(() => {});
  }
  useEffect(reloadDecks, []);

  // options for the current language (plus language-agnostic decks)
  const options = useMemo(
    () => decks.filter((d) => !d.language || d.language === language),
    [decks, language],
  );
  const defaultDeck = decks.find((d) => d.is_default && d.language === language);

  async function newDeck() {
    const name = prompt(`New deck name (${language === "de" ? "German" : "English"})`);
    if (!name?.trim()) return;
    try {
      const d = await api.createDeck(name.trim(), language);
      reloadDecks();
      setDeckId(String(d.id));
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!word.trim()) return;
    onSubmit({
      word: word.trim(),
      language,
      context: context.trim() || undefined,
      deck_id: deckId ? Number(deckId) : undefined,
      use_query_as_prompt: keepPrompt,
    });
  }

  return (
    <form className="lookup" onSubmit={submit}>
      <div className="row">
        <input
          autoFocus
          placeholder="A word, or its meaning in any language…"
          value={word}
          onChange={(e) => setWord(e.target.value)}
        />
        <select value={language} onChange={(e) => setLanguage(e.target.value as Language)}>
          <option value="en">English</option>
          <option value="de">German</option>
        </select>
        <button type="submit" disabled={loading}>
          {loading ? "Generating…" : "Look up → card"}
        </button>
      </div>

      <div className="row">
        <select
          className="deck-select"
          value={deckId}
          onChange={(e) => setDeckId(e.target.value)}
        >
          <option value="">Default deck ({defaultDeck?.name ?? `new-${language}`})</option>
          {options
            .filter((d) => !(d.is_default && d.language === language))
            .map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
        </select>
        <button type="button" onClick={newDeck}>
          + New deck
        </button>
      </div>

      <textarea
        placeholder="Optional: paste the sentence you met this word in — examples will match that context"
        value={context}
        onChange={(e) => setContext(e.target.value)}
        rows={2}
      />

      <label className="lookup-check">
        <input
          type="checkbox"
          checked={keepPrompt}
          onChange={(e) => setKeepPrompt(e.target.checked)}
        />
        If I search in another language, keep my text as the card prompt (front)
      </label>
    </form>
  );
}
