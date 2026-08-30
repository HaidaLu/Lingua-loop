import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import type { DeckOut, Language } from "../types";

interface Pending {
  id: string;
  file: File;
  url: string;
}

const lines = (v: string) => v.split("\n").map((s) => s.trim()).filter(Boolean);

export default function AddCard() {
  const [params] = useSearchParams();
  const [decks, setDecks] = useState<DeckOut[]>([]);
  const [deckId, setDeckId] = useState(params.get("deck_id") ?? "");
  const [language, setLanguage] = useState<Language>("de");
  const [f, setF] = useState({
    word: "",
    prompt: "",
    translation: "",
    definitions: "",
    examples: "",
    pos: "",
    collocations: "",
    gender: "",
    plural_form: "",
    case_notes: "",
    mnemonic: "",
  });
  const [advanced, setAdvanced] = useState(false);
  const [files, setFiles] = useState<Pending[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF((s) => ({ ...s, [k]: e.target.value }));

  useEffect(() => {
    api.listDecks().then((d) => {
      setDecks(d);
      if (!deckId && !params.get("deck_id")) {
        // pick default deck for current language
        const def = d.find((x) => x.is_default && x.language === language);
        if (def) setDeckId(String(def.id));
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => files.forEach((p) => URL.revokeObjectURL(p.url));
  }, [files]);

  function addFiles(list: FileList | File[]) {
    const ok = [...list].filter((x) => /^(image|audio|video)\//.test(x.type));
    if (!ok.length) return;
    setFiles((cur) => [
      ...cur,
      ...ok.map((file) => ({
        id: `${Date.now()}-${Math.random()}`,
        file,
        url: URL.createObjectURL(file),
      })),
    ]);
  }

  // paste an image from anywhere on the page
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      const items = e.clipboardData?.items;
      if (!items) return;
      const imgs: File[] = [];
      for (const it of items) {
        if (it.type.startsWith("image/")) {
          const file = it.getAsFile();
          if (file)
            imgs.push(
              new File([file], file.name || `pasted-${Date.now()}.png`, { type: file.type }),
            );
        }
      }
      if (imgs.length) addFiles(imgs);
    }
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, []);

  const options = useMemo(
    () => decks.filter((d) => !d.language || d.language === language),
    [decks, language],
  );

  async function submit(e: FormEvent, keepAdding: boolean) {
    e.preventDefault();
    if (!f.word.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.createCard({
        deck_id: deckId ? Number(deckId) : undefined,
        language,
        word: f.word.trim(),
        prompt: f.prompt.trim() || null,
        translation: f.translation.trim() || null,
        definitions: lines(f.definitions),
        examples: lines(f.examples),
        pos: f.pos.trim() || null,
        collocations: lines(f.collocations),
        gender: (f.gender || null) as CardCreateGender,
        plural_form: f.plural_form.trim() || null,
        case_notes: f.case_notes.trim() || null,
        mnemonic: f.mnemonic.trim() || null,
      });
      for (const p of files) {
        try {
          await api.uploadMedia(res.word.id, p.file);
        } catch {
          /* keep going */
        }
      }
      setAdded((a) => [f.word.trim(), ...a].slice(0, 8));
      files.forEach((p) => URL.revokeObjectURL(p.url));
      setFiles([]);
      setF((s) => ({ ...s, word: "", prompt: "", translation: "", definitions: "", examples: "", collocations: "", case_notes: "", mnemonic: "", pos: "", gender: "", plural_form: "" }));
      if (!keepAdding) {
        window.location.href = `/cards?deck_id=${res.word.deck_id}`;
        return;
      }
      inputRef.current?.focus();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <h1>Add a card</h1>
      <p className="muted">
        Type the fields yourself — no AI. Attach or paste images / audio / video. ·{" "}
        <Link to="/cards">Card library</Link>
      </p>
      {error && <div className="error">{error}</div>}
      {added.length > 0 && (
        <p className="muted">✓ Added: {added.join(", ")}</p>
      )}

      <form className="edit-form" onSubmit={(e) => submit(e, true)}>
        <div className="de-fields">
          <label>
            Deck
            <select value={deckId} onChange={(e) => setDeckId(e.target.value)}>
              {options.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Language
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as Language)}
            >
              <option value="en">English</option>
              <option value="de">German</option>
            </select>
          </label>
        </div>

        <label>
          Word / headword *
          <input ref={inputRef} value={f.word} onChange={set("word")} required autoFocus />
        </label>
        <label>
          Prompt (front text, optional)
          <textarea rows={2} value={f.prompt} onChange={set("prompt")} />
        </label>
        <label>
          Meaning (one line)
          <input value={f.translation} onChange={set("translation")} />
        </label>
        <label>
          Definitions (one per line)
          <textarea rows={2} value={f.definitions} onChange={set("definitions")} />
        </label>
        <label>
          Examples (one per line)
          <textarea rows={3} value={f.examples} onChange={set("examples")} />
        </label>

        {language === "de" && (
          <div className="de-fields">
            <label>
              Article
              <select value={f.gender} onChange={set("gender")}>
                <option value="">(none)</option>
                <option value="der">der</option>
                <option value="die">die</option>
                <option value="das">das</option>
              </select>
            </label>
            <label>
              Plural
              <input value={f.plural_form} onChange={set("plural_form")} />
            </label>
          </div>
        )}

        <button type="button" className="linkish" onClick={() => setAdvanced((v) => !v)}>
          {advanced ? "▾" : "▸"} more fields
        </button>
        {advanced && (
          <>
            <label>Part of speech<input value={f.pos} onChange={set("pos")} /></label>
            <label>Collocations (one per line)<textarea rows={2} value={f.collocations} onChange={set("collocations")} /></label>
            <label>Case / usage<textarea rows={2} value={f.case_notes} onChange={set("case_notes")} /></label>
            <label>Mnemonic<textarea rows={2} value={f.mnemonic} onChange={set("mnemonic")} /></label>
          </>
        )}

        <label>Media (image / audio / video — drop, browse, or paste)</label>
        <div
          className="media-drop"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            addFiles(e.dataTransfer.files);
          }}
          onClick={() => document.getElementById("addcard-file")?.click()}
        >
          <input
            id="addcard-file"
            type="file"
            multiple
            accept="image/*,audio/*,video/*"
            style={{ display: "none" }}
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
          {files.length === 0 ? (
            <span className="muted">Click to browse, drop files here, or paste an image (Cmd/Ctrl+V)</span>
          ) : (
            <div className="media-previews">
              {files.map((p) => (
                <span key={p.id} className="media-item">
                  {p.file.type.startsWith("image/") ? (
                    <img src={p.url} alt="" />
                  ) : p.file.type.startsWith("video/") ? (
                    <video src={p.url} controls preload="metadata" />
                  ) : (
                    <audio src={p.url} controls />
                  )}
                  <button
                    type="button"
                    className="media-del"
                    onClick={(e) => {
                      e.stopPropagation();
                      URL.revokeObjectURL(p.url);
                      setFiles((cur) => cur.filter((x) => x.id !== p.id));
                    }}
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="form-actions">
          <button type="submit" className="primary" disabled={busy || !f.word.trim()}>
            {busy ? "Adding…" : "Add & keep going"}
          </button>
          <button type="button" disabled={busy || !f.word.trim()} onClick={(e) => submit(e, false)}>
            Add & view deck
          </button>
        </div>
      </form>
    </main>
  );
}

type CardCreateGender = "der" | "die" | "das" | null;
