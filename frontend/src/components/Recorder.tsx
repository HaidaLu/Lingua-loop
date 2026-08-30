import { useRef, useState } from "react";
import { api } from "../api";
import type { MediaOut } from "../types";

type State = "idle" | "recording" | "saving";

export default function Recorder({
  wordId,
  onDone,
}: {
  wordId: number;
  onDone: (m: MediaOut) => void;
}) {
  const [state, setState] = useState<State>("idle");
  const [err, setErr] = useState<string | null>(null);
  const mrRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function start() {
    setErr(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setErr("Recording isn't supported in this browser");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data);
      };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: mr.mimeType || "audio/webm" });
        setState("saving");
        try {
          onDone(await api.uploadRecording(wordId, blob));
          setState("idle");
        } catch (e) {
          setErr(e instanceof Error ? e.message : String(e));
          setState("idle");
        }
      };
      mrRef.current = mr;
      mr.start();
      setState("recording");
    } catch {
      setErr("Microphone access was denied");
    }
  }

  return (
    <div className="recorder">
      {state === "idle" && (
        <button type="button" onClick={start}>
          🎙 Record
        </button>
      )}
      {state === "recording" && (
        <button type="button" className="rec-live" onClick={() => mrRef.current?.stop()}>
          ⏹ Stop &amp; save
        </button>
      )}
      {state === "saving" && <span className="muted">saving…</span>}
      {err && <span className="rec-err">{err}</span>}
    </div>
  );
}
