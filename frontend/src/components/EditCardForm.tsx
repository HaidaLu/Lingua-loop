import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { DeckOut, GenerateCardResponse, WordUpdate } from "../types";

function lines(v: string[]): string {
  return v.join("\n");
}
function parseLines(v: string): string[] {
  return v.split("\n").map((s) => s.trim()).filter(Boolean);
}

export default function EditCardForm({
  data,
  busy,
  onCancel,
  onSave,
}: {
  data: GenerateCardResponse;
  busy: boolean;
  onCancel: () => void;
  onSave: (patch: WordUpdate) => void;
}) {
  const w = data.word;
  const [decks, setDecks] = useState<DeckOut[]>([]);
  const [f, setF] = useState({
    word: w.word,
    deck_id: w.deck_id ? String(w.deck_id) : "",
    prompt: w.prompt ?? "",
    pos: w.pos ?? "",
    translation: w.translation ?? "",
    definitions: lines(w.definitions),
    examples: lines(w.examples),
    collocations: lines(w.collocations),
    gender: w.gender ?? "",
    plural_form: w.plural_form ?? "",
    case_notes: w.case_notes ?? "",
    mnemonic: w.mnemonic ?? "",
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    api.listDecks().then(setDecks).catch(() => {});
  }, []);

  function submit(e: FormEvent) {
    e.preventDefault();
    onSave({
      word: f.word.trim(),
      deck_id: f.deck_id ? Number(f.deck_id) : undefined,
      prompt: f.prompt.trim() || null,
      pos: f.pos.trim() || null,
      translation: f.translation.trim() || null,
      definitions: parseLines(f.definitions),
      examples: parseLines(f.examples),
      collocations: parseLines(f.collocations),
      gender: (f.gender || null) as WordUpdate["gender"],
      plural_form: f.plural_form.trim() || null,
      case_notes: f.case_notes.trim() || null,
      mnemonic: f.mnemonic.trim() || null,
    });
  }

  return (
    <form className="edit-form" onSubmit={submit}>
      <label>Word<input value={f.word} onChange={set("word")} required /></label>
      <label>
        Deck
        <select value={f.deck_id} onChange={set("deck_id")}>
          {decks
            .filter((d) => !d.language || d.language === w.language)
            .map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
        </select>
      </label>
      <label>
        Prompt (custom review front, optional)
        <textarea rows={2} value={f.prompt} onChange={set("prompt")} />
      </label>
      <label>Part of speech<input value={f.pos} onChange={set("pos")} /></label>
      <label>Meaning (one line)<input value={f.translation} onChange={set("translation")} /></label>
      <label>Definitions (one per line)<textarea rows={3} value={f.definitions} onChange={set("definitions")} /></label>
      <label>Examples (one per line)<textarea rows={4} value={f.examples} onChange={set("examples")} /></label>
      <label>Collocations (one per line)<textarea rows={3} value={f.collocations} onChange={set("collocations")} /></label>
      {w.language === "de" && (
        <div className="de-fields">
          <label>
            Article
            <select value={f.gender} onChange={set("gender")}>
              <option value="">(none / not a noun)</option>
              <option value="der">der</option>
              <option value="die">die</option>
              <option value="das">das</option>
            </select>
          </label>
          <label>Plural<input value={f.plural_form} onChange={set("plural_form")} /></label>
        </div>
      )}
      <label>Case / usage<textarea rows={2} value={f.case_notes} onChange={set("case_notes")} /></label>
      <label>Mnemonic<textarea rows={2} value={f.mnemonic} onChange={set("mnemonic")} /></label>

      <div className="form-actions">
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </form>
  );
}
