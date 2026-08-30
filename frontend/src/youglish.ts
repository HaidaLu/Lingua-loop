// Loader for the official YouGlish JS Widget API.
// Docs: https://youglish.com/api — the script calls global onYouglishAPIReady when ready.

declare global {
  interface Window {
    YG?: YGNamespace;
    onYouglishAPIReady?: () => void;
  }
}

export interface YGWidget {
  fetch(query: string, lang: string, accent?: string): void;
  next(): void;
  previous?(): void;
  pause?(): void;
}

interface YGNamespace {
  Widget: new (
    elementId: string,
    opts: {
      width?: number;
      components?: number; // bitmask: 1 search box | 2 caption | 4 video info | 8 controls (default 15)
      bkg?: number;
      events?: Record<string, (e: unknown) => void>;
    },
  ) => YGWidget;
}

const SRC = "https://youglish.com/public/emb/widget.js";
let readyPromise: Promise<YGNamespace> | null = null;

export function loadYouglish(): Promise<YGNamespace> {
  if (readyPromise) return readyPromise;

  readyPromise = new Promise((resolve, reject) => {
    if (window.YG) return resolve(window.YG);

    window.onYouglishAPIReady = () => {
      if (window.YG) resolve(window.YG);
      else reject(new Error("YouGlish loaded but the YG namespace is missing"));
    };

    const s = document.createElement("script");
    s.src = SRC;
    s.async = true;
    s.onerror = () => {
      readyPromise = null;
      reject(new Error("Failed to load YouGlish widget.js (network error or blocked)"));
    };
    document.head.appendChild(s);
  });

  return readyPromise;
}

export function ygLangName(language: "en" | "de"): string {
  return language === "de" ? "german" : "english";
}

// YouGlish's API rejects long / punctuation-heavy queries with HTTP 400. Reduce
// whatever the card carries to something it will accept; return "" if nothing usable.
export function sanitizeYouglishQuery(raw: string): string {
  let s = (raw || "").split("\n")[0];
  s = s.replace(/\[[^\]]*\]/g, " "); // [sound:...] and other bracket tags
  s = s.replace(/[()[\]{}"'|<>*_/\\]/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  s = s.replace(/[\s,;:–—-]+(der|die|das)$/i, ""); // trailing German article marker
  s = s.replace(/^[^\p{L}]+|[.!?,;:]+$/gu, "").trim(); // trim edge punctuation
  if (/[㐀-鿿]/.test(s)) return ""; // CJK: not a Latin-script query
  const words = s.split(" ").filter(Boolean);
  if (words.length > 4) return ""; // a whole sentence — no good headword to guess here
  return words.join(" ").slice(0, 60);
}
