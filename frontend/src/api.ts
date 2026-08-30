import type {
  AnkiCommitRequest,
  AnkiCommitResponse,
  AnkiPreviewResponse,
  AuthStatus,
  CardCreate,
  DeckOut,
  DueQueueResponse,
  GenerateCardResponse,
  HeatmapResponse,
  Language,
  MediaOut,
  Rating,
  ReviewStats,
  TokenResponse,
  WordListResponse,
  WordUpdate,
  YouglishTermResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? ""; // default: go through the vite proxy

let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAuthToken(t: string | null) {
  authToken = t;
}
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });

  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    onUnauthorized?.();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const qs = (o: Record<string, string | number | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v != null && v !== "") p.set(k, String(v));
  return p.toString();
};

export const api = {
  health: () => req<{ llm_provider: string; llm_model: string | null }>("/api/health"),

  // ---- auth ----
  authStatus: () => req<AuthStatus>("/api/auth/status"),
  register: (email: string, password: string) =>
    req<TokenResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    req<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => req<TokenResponse>("/api/auth/me"),

  // ---- decks ----
  listDecks: () => req<DeckOut[]>("/api/decks"),
  createDeck: (name: string, language?: Language) =>
    req<DeckOut>("/api/decks", { method: "POST", body: JSON.stringify({ name, language }) }),
  renameDeck: (id: number, name: string) =>
    req<DeckOut>(`/api/decks/${id}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteDeck: (id: number, keepCards = false) =>
    req<void>(`/api/decks/${id}?${qs({ keep_cards: keepCards ? "true" : "" })}`, {
      method: "DELETE",
    }),

  // ---- cards ----
  generateCard: (input: {
    word: string;
    language: Language;
    context?: string;
    deck_id?: number;
    use_query_as_prompt?: boolean;
  }) =>
    req<GenerateCardResponse>("/api/generate-card", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  listWords: (
    params: { language?: Language; deck_id?: number; q?: string; offset?: number; limit?: number } = {},
  ) => req<WordListResponse>(`/api/words?${qs(params)}`),
  createCard: (body: CardCreate) =>
    req<GenerateCardResponse>("/api/cards", { method: "POST", body: JSON.stringify(body) }),
  getCard: (id: number) => req<GenerateCardResponse>(`/api/cards/${id}`),
  updateCard: (id: number, patch: WordUpdate) =>
    req<GenerateCardResponse>(`/api/cards/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteCard: (id: number) => req<void>(`/api/cards/${id}`, { method: "DELETE" }),
  youglishTerm: (id: number) =>
    req<YouglishTermResponse>(`/api/cards/${id}/youglish-term`, { method: "POST" }),

  // ---- review ----
  due: (params: { language?: Language; deck_id?: number; limit?: number } = {}) =>
    req<DueQueueResponse>(`/api/review/due?${qs(params)}`),
  submitReview: (word_id: number, rating: Rating) =>
    req<{ word_id: number; fsrs: unknown }>("/api/review/submit", {
      method: "POST",
      body: JSON.stringify({ word_id, rating }),
    }),
  stats: () => req<ReviewStats>("/api/review/stats"),
  heatmap: (days = 365) =>
    req<HeatmapResponse>(
      `/api/review/heatmap?${qs({ days, tz_offset_minutes: -new Date().getTimezoneOffset() })}`,
    ),

  // ---- anki import ----
  ankiPreview: async (file: File): Promise<AnkiPreviewResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${BASE}/api/import/anki/preview`, {
      method: "POST",
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
      body: fd,
    });
    if (res.status === 401) onUnauthorized?.();
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `${res.status} ${res.statusText}`);
    }
    return res.json();
  },
  ankiCommit: (body: AnkiCommitRequest) =>
    req<AnkiCommitResponse>("/api/import/anki/commit", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // ---- media ----
  getMediaBlob: async (id: number): Promise<Blob> => {
    const res = await fetch(`${BASE}/api/media/${id}`, {
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
    });
    if (res.status === 401) onUnauthorized?.();
    if (!res.ok) throw new Error(`media ${id}: ${res.status}`);
    return res.blob();
  },
  uploadRecording: async (wordId: number, blob: Blob): Promise<MediaOut> => {
    const fd = new FormData();
    fd.append("file", blob, "recording.webm");
    const res = await fetch(`${BASE}/api/cards/${wordId}/recordings`, {
      method: "POST",
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
      body: fd,
    });
    if (res.status === 401) onUnauthorized?.();
    if (!res.ok) {
      const b = await res.json().catch(() => ({}));
      throw new Error(b.detail || `${res.status} ${res.statusText}`);
    }
    return res.json();
  },
  uploadMedia: async (wordId: number, file: File): Promise<MediaOut> => {
    const fd = new FormData();
    fd.append("file", file, file.name || "upload");
    const res = await fetch(`${BASE}/api/cards/${wordId}/media`, {
      method: "POST",
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
      body: fd,
    });
    if (res.status === 401) onUnauthorized?.();
    if (!res.ok) {
      const b = await res.json().catch(() => ({}));
      throw new Error(b.detail || `${res.status} ${res.statusText}`);
    }
    return res.json();
  },
  deleteMedia: (id: number) => req<void>(`/api/media/${id}`, { method: "DELETE" }),
};
