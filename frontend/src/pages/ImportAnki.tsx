import { useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { AnkiCommitResponse, AnkiPreviewResponse, Language } from "../types";

const NONE = "__none__";

// mirror of the backend's word extraction so the sample preview matches
const SEPARATORS = /\s*[–—:,;/|]\s*|\s+-\s+|\t|\n/;
function extractWord(raw: string, mode: "whole" | "before_separator"): string {
  let text = (raw.split("\n")[0] ?? "").trim();
  if (mode === "before_separator") text = text.split(SEPARATORS)[0] ?? text;
  return text.trim();
}

function guessLanguage(text: string): "en" | "de" {
  const t = text.toLowerCase();
  if (/\b(de|deutsch|german|nicos)\b/.test(t)) return "de";
  if (/\b(en|english|englisch)\b/.test(t)) return "en";
  return "de";
}

export default function ImportAnki() {
  const [preview, setPreview] = useState<AnkiPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnkiCommitResponse | null>(null);

  // mapping form
  const [noteType, setNoteType] = useState("");
  const [deckName, setDeckName] = useState("");
  const [language, setLanguage] = useState<Language>("de");
  const [wordField, setWordField] = useState("");
  const [wordExtract, setWordExtract] = useState<"whole" | "before_separator">("whole");
  const [promptField, setPromptField] = useState(NONE);
  const [meaningField, setMeaningField] = useState(NONE);
  const [examplesField, setExamplesField] = useState(NONE);
  const [importProgress, setImportProgress] = useState(true);
  const [onDuplicate, setOnDuplicate] = useState<"skip" | "overwrite">("skip");

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const p = await api.ankiPreview(file);
      setPreview(p);
      const firstType = [...p.note_types].sort((a, b) => b.note_count - a.note_count)[0];
      setNoteType(firstType?.name ?? "");
      setDeckName(p.suggested_deck_name);
      setLanguage(guessLanguage([p.suggested_deck_name, ...p.anki_decks].join(" ")));
      setWordField(firstType?.fields[0] ?? "");
      setWordExtract("whole");
      setPromptField(NONE);
      setMeaningField(firstType?.fields[1] ?? NONE);
      setExamplesField(firstType?.fields[2] ?? NONE);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const activeType = useMemo(
    () => preview?.note_types.find((t) => t.name === noteType),
    [preview, noteType],
  );
  const sample = useMemo(
    () => preview?.samples.find((s) => s.note_type === noteType),
    [preview, noteType],
  );

  async function commit() {
    if (!preview || !activeType) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.ankiCommit({
        import_id: preview.import_id,
        deck_name: deckName.trim(),
        language,
        note_type: noteType,
        word_field: wordField,
        word_extract: wordExtract,
        prompt_field: promptField === NONE ? null : promptField,
        meaning_field: meaningField === NONE ? null : meaningField,
        examples_field: examplesField === NONE ? null : examplesField,
        import_progress: importProgress,
        on_duplicate: onDuplicate,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <main className="page">
        <h1>Import complete</h1>
        <p>
          Deck “{result.deck_name}”: <b>{result.imported}</b> new
          {result.updated > 0 && <> · <b>{result.updated}</b> updated</>}
          {result.skipped > 0 && (
            <> · {result.skipped} skipped (already in your collection, or empty)</>
          )}
        </p>
        <div className="cta-row">
          <Link className="btn primary" to={`/cards?deck_id=${result.deck_id}`}>
            View deck
          </Link>
          <Link className="btn" to={`/review?deck_id=${result.deck_id}`}>
            Review it
          </Link>
          <button
            onClick={() => {
              setPreview(null);
              setResult(null);
            }}
          >
            Import another
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <h1>Import from Anki</h1>
      <p className="muted">
        Export a deck from Anki (File → Export → Anki Deck Package .apkg). To keep your review
        progress, tick <b>“Include scheduling information”</b> in the export dialog.
      </p>

      {error && <div className="error">{error}</div>}

      {!preview ? (
        <label className="file-drop">
          <input type="file" accept=".apkg,.colpkg" onChange={onFile} disabled={loading} />
          {loading ? "Reading…" : "Choose an .apkg file"}
        </label>
      ) : (
        <>
          <p className="muted">
            {preview.total_notes} notes · {preview.notes_with_progress} with review progress
            {preview.anki_decks.length > 0 && ` · Anki decks: ${preview.anki_decks.join(", ")}`}
          </p>
          {preview.notes_with_progress === 0 && preview.total_notes > 0 && (
            <div className="warn">
              This file has no Anki scheduling data, so every card will import as <b>New</b>. To keep
              your progress, re-export from Anki with <b>“Include scheduling information”</b> checked.
            </div>
          )}

          <div className="edit-form">
            {preview.note_types.length > 1 && (
              <label>
                Note type
                <select value={noteType} onChange={(e) => setNoteType(e.target.value)}>
                  {preview.note_types.map((t) => (
                    <option key={t.name} value={t.name}>
                      {t.name} ({t.note_count})
                    </option>
                  ))}
                </select>
              </label>
            )}

            <label>
              Deck name
              <input value={deckName} onChange={(e) => setDeckName(e.target.value)} />
            </label>
            <label>
              Language of this deck
              <select value={language} onChange={(e) => setLanguage(e.target.value as Language)}>
                <option value="en">English</option>
                <option value="de">German</option>
              </select>
              <span className="field-hint">
                every imported card is tagged with this — drives YouGlish, German gender, review filters
              </span>
            </label>

            <FieldPick
              label="Prompt field (shown on the review front, optional)"
              fields={activeType?.fields ?? []}
              value={promptField}
              onChange={setPromptField}
              allowNone
            />

            <div className="de-fields">
              <FieldPick
                label="Word field — the target-language word (required)"
                fields={activeType?.fields ?? []}
                value={wordField}
                onChange={setWordField}
              />
              <label>
                Extract
                <select
                  value={wordExtract}
                  onChange={(e) => setWordExtract(e.target.value as "whole" | "before_separator")}
                >
                  <option value="whole">whole field</option>
                  <option value="before_separator">before – : ,</option>
                </select>
              </label>
            </div>

            <FieldPick label="Meaning field" fields={activeType?.fields ?? []} value={meaningField} onChange={setMeaningField} allowNone />
            <FieldPick label="Examples field" fields={activeType?.fields ?? []} value={examplesField} onChange={setExamplesField} allowNone />

            <label className="checkbox">
              <input
                type="checkbox"
                checked={importProgress}
                onChange={(e) => setImportProgress(e.target.checked)}
              />
              Import review progress (approximate from Anki interval / ease)
            </label>

            <label>
              If a word is already in your collection
              <select
                value={onDuplicate}
                onChange={(e) => setOnDuplicate(e.target.value as "skip" | "overwrite")}
              >
                <option value="skip">Skip it</option>
                <option value="overwrite">Overwrite it (content + progress + deck)</option>
              </select>
            </label>
          </div>

          {sample && (
            <div className="sample-preview">
              <h3>Sample note → card</h3>
              {promptField !== NONE && (
                <div className="sample-row">
                  <span className="sample-label">Prompt</span>
                  <span>{sample.fields[promptField] || <em>(empty)</em>}</span>
                </div>
              )}
              <div className="sample-row">
                <span className="sample-label">Word</span>
                <span>{extractWord(sample.fields[wordField] ?? "", wordExtract) || <em>(empty)</em>}</span>
              </div>
              {meaningField !== NONE && (
                <div className="sample-row">
                  <span className="sample-label">Meaning</span>
                  <span>{sample.fields[meaningField] || <em>(empty)</em>}</span>
                </div>
              )}
              {examplesField !== NONE && (
                <div className="sample-row">
                  <span className="sample-label">Examples</span>
                  <span>{sample.fields[examplesField] || <em>(empty)</em>}</span>
                </div>
              )}
            </div>
          )}

          <div className="form-actions">
            <button
              className="primary"
              disabled={loading || !wordField || !deckName.trim()}
              onClick={commit}
            >
              {loading ? "Importing…" : `Import ${activeType?.note_count ?? 0} notes`}
            </button>
            <button onClick={() => setPreview(null)} disabled={loading}>
              Cancel
            </button>
          </div>
        </>
      )}
    </main>
  );
}

function FieldPick({
  label,
  fields,
  value,
  onChange,
  allowNone,
}: {
  label: string;
  fields: string[];
  value: string;
  onChange: (v: string) => void;
  allowNone?: boolean;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {allowNone && <option value={NONE}>— none —</option>}
        {fields.map((f) => (
          <option key={f} value={f}>
            {f}
          </option>
        ))}
      </select>
    </label>
  );
}
