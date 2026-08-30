import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { MediaOut } from "../types";

function typeOf(mime: string): "image" | "video" | "audio" {
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  return "audio";
}

export default function MediaItem({
  media,
  label,
  onDelete,
}: {
  media: MediaOut;
  label?: string;
  onDelete?: () => void;
}) {
  const t = typeOf(media.mime);
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(false);
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  async function load() {
    if (url) return;
    setBusy(true);
    setErr(false);
    try {
      const blob = await api.getMediaBlob(media.id);
      const u = URL.createObjectURL(blob);
      urlRef.current = u;
      setUrl(u);
    } catch {
      setErr(true);
    } finally {
      setBusy(false);
    }
  }

  // images load immediately; audio/video load on click
  useEffect(() => {
    if (t === "image") load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const del = onDelete && (
    <button className="media-del" onClick={onDelete} title="remove">
      ✕
    </button>
  );

  if (t === "image") {
    return (
      <span className="media-item media-image">
        {url ? (
          <img src={url} alt={label || "image"} />
        ) : (
          <span className="muted">{err ? "⚠ image" : "…"}</span>
        )}
        {del}
      </span>
    );
  }

  if (t === "video") {
    return (
      <span className="media-item media-video">
        {url ? (
          <video src={url} controls preload="metadata" />
        ) : (
          <button onClick={load} disabled={busy}>
            {busy ? "…" : err ? "⚠ retry" : "▶"} {label || "Video"}
          </button>
        )}
        {del}
      </span>
    );
  }

  return (
    <span className="media-item media-audio">
      {url ? (
        <audio src={url} controls preload="auto" autoPlay />
      ) : (
        <button onClick={load} disabled={busy}>
          {busy ? "…" : err ? "⚠ retry" : "▶"}
          {label ? ` ${label}` : ""}
        </button>
      )}
      {del}
    </span>
  );
}
