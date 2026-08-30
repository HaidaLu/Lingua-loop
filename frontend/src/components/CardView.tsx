import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { GenerateCardResponse, MediaOut } from "../types";
import YouglishWidget from "./YouglishWidget";
import ErrorBoundary from "./ErrorBoundary";
import MediaItem from "./MediaItem";
import Recorder from "./Recorder";
import { api } from "../api";

const GENDER_COLOR: Record<string, string> = {
  der: "#2563eb",
  die: "#db2777",
  das: "#16a34a",
};

const isImage = (m: MediaOut) => m.mime.startsWith("image/");
const isVideo = (m: MediaOut) => m.mime.startsWith("video/");
const isAudio = (m: MediaOut) => m.mime.startsWith("audio/") || m.mime === "";

export default function CardView({
  data,
  youglishOpen = false,
}: {
  data: GenerateCardResponse;
  youglishOpen?: boolean;
}) {
  const { word: w, fsrs } = data;
  const [ygOpen, setYgOpen] = useState(youglishOpen);
  const [media, setMedia] = useState<MediaOut[]>(w.media ?? []);

  useEffect(() => {
    setMedia(w.media ?? []);
  }, [w.id, w.media]);

  const images = media.filter(isImage);
  const videos = media.filter(isVideo);
  const clips = media.filter((m) => isAudio(m) && m.kind !== "user_recording");
  const recordings = media.filter((m) => m.kind === "user_recording");

  async function removeMedia(id: number) {
    try {
      await api.deleteMedia(id);
      setMedia((ms) => ms.filter((m) => m.id !== id));
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="card">
      <div className="card-head">
        <h2>
          {w.language === "de" && w.gender && (
            <span className="gender" style={{ color: GENDER_COLOR[w.gender] }}>
              {w.gender}{" "}
            </span>
          )}
          {w.word}
          {w.plural_form && <span className="plural"> · pl. {w.plural_form}</span>}
          {clips.length > 0 && (
            <span className="head-audio">
              <MediaItem media={clips[0]} label="" />
            </span>
          )}
        </h2>
        <div className="badges">
          <span className="badge">{w.language.toUpperCase()}</span>
          {w.deck_name && <span className="badge">🗂 {w.deck_name}</span>}
          {w.pos && <span className="badge">{w.pos}</span>}
          <span className="badge">{data.llm_provider}</span>
          <span className="badge">{data.created ? "new" : "updated"}</span>
        </div>
      </div>

      {w.prompt && (
        <div className="prompt-block">
          <span className="prompt-tag">prompt</span>
          {w.prompt}
        </div>
      )}

      {w.translation && <p className="translation">{w.translation}</p>}

      {images.length > 0 && (
        <div className="media-gallery">
          {images.map((m) => (
            <MediaItem key={m.id} media={m} onDelete={() => removeMedia(m.id)} />
          ))}
        </div>
      )}

      {clips.length > 1 && (
        <div className="media-row">
          {clips.map((m, i) => (
            <MediaItem key={m.id} media={m} label={`Clip ${i + 1}`} />
          ))}
        </div>
      )}

      <Section title="Definitions">
        <ul>{w.definitions.map((d, i) => <li key={i}>{d}</li>)}</ul>
      </Section>

      <Section title="Examples">
        <ul>{w.examples.map((e, i) => <li key={i}>{e}</li>)}</ul>
      </Section>

      {w.collocations.length > 0 && (
        <Section title="Collocations">
          <div className="chips">
            {w.collocations.map((c, i) => <span key={i} className="chip">{c}</span>)}
          </div>
        </Section>
      )}

      {w.case_notes && <Section title="Case / usage"><p>{w.case_notes}</p></Section>}
      {w.mnemonic && <Section title="Mnemonic"><p>{w.mnemonic}</p></Section>}

      {videos.length > 0 && (
        <Section title="Video">
          <div className="media-row">
            {videos.map((m, i) => (
              <MediaItem key={m.id} media={m} label={`Video ${i + 1}`} onDelete={() => removeMedia(m.id)} />
            ))}
          </div>
        </Section>
      )}

      <Section title="Pronunciation practice">
        <div className="practice-row">
          <Recorder wordId={w.id} onDone={(m) => setMedia((ms) => [...ms, m])} />
          {recordings.map((m, i) => (
            <MediaItem key={m.id} media={m} label={`Take ${i + 1}`} onDelete={() => removeMedia(m.id)} />
          ))}
        </div>
      </Section>

      <div className="section">
        <button className="yg-toggle" onClick={() => setYgOpen((v) => !v)}>
          {ygOpen ? "▾" : "▸"} YouGlish · real pronunciation clips from YouTube
        </button>
        {ygOpen && (
          <ErrorBoundary
            fallback={<p className="muted">The YouGlish widget failed to load.</p>}
          >
            <YouglishWidget
              key={w.id}
              word={w.word}
              language={w.language}
              wordId={w.id}
              storedTerm={w.youglish_term}
            />
          </ErrorBoundary>
        )}
      </div>

      <div className="fsrs">
        FSRS: <b>{fsrs.state}</b> · due {new Date(fsrs.due_date).toLocaleString()} · reps {fsrs.reps} · lapses {fsrs.lapses}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="section">
      <h3>{title}</h3>
      {children}
    </div>
  );
}
