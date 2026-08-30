export type Language = "en" | "de";
export type Rating = 1 | 2 | 3 | 4; // again / hard / good / easy

export interface TokenResponse {
  access_token: string;
  token_type: string;
  email: string;
}

export interface AuthStatus {
  registered: boolean;
}

export interface DeckOut {
  id: number;
  name: string;
  language: Language | null;
  is_default: boolean;
  card_count: number;
  new_count: number;
  learn_count: number;
  due_count: number;
}

export interface MediaOut {
  id: number;
  kind: "word" | "example" | "extra" | "user_recording" | "image" | "audio" | "video";
  mime: string;
  source: "anki_import" | "recording" | "upload";
}

export interface CardCreate {
  deck_id?: number;
  language: Language;
  word: string;
  prompt?: string | null;
  pos?: string | null;
  translation?: string | null;
  definitions?: string[];
  examples?: string[];
  collocations?: string[];
  gender?: string | null;
  plural_form?: string | null;
  case_notes?: string | null;
  mnemonic?: string | null;
}

export interface WordOut {
  id: number;
  word: string;
  language: Language;
  youglish_term?: string | null;
  deck_id: number | null;
  deck_name: string | null;
  prompt: string | null;
  media: MediaOut[];
  pos: string | null;
  translation: string | null;
  definitions: string[];
  examples: string[];
  collocations: string[];
  gender: string | null;
  plural_form: string | null;
  case_notes: string | null;
  mnemonic: string | null;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface FsrsState {
  state: string;
  due_date: string;
  stability: number | null;
  difficulty: number | null;
  reps: number;
  lapses: number;
  last_review: string | null;
}

export interface GenerateCardResponse {
  word: WordOut;
  fsrs: FsrsState;
  llm_provider: string;
  created: boolean;
}

export interface YouglishTermResponse {
  term: string;
  resolved_by: "stored" | "word" | "llm" | "fallback";
}

export interface WordListResponse {
  items: WordOut[];
  total: number;
  offset: number;
  limit: number;
}

export interface ReviewItem {
  word: WordOut;
  fsrs: FsrsState;
}

export interface DueQueueResponse {
  items: ReviewItem[];
  total_due: number;
}

export interface ReviewStats {
  total_cards: number;
  new_cards: number;
  learn_now: number;
  due_now: number;
  reviewed_today: number;
  by_language: Record<string, number>;
}

export interface HeatmapDay {
  date: string;
  count: number;
  reviews: number;
  added: number;
}

export interface HeatmapResponse {
  days: HeatmapDay[];
  current_streak: number;
  longest_streak: number;
  active_days: number;
  total_reviews: number;
}

export interface AnkiNoteType {
  name: string;
  fields: string[];
  note_count: number;
}

export interface AnkiSample {
  note_type: string;
  fields: Record<string, string>;
}

export interface AnkiPreviewResponse {
  import_id: string;
  note_types: AnkiNoteType[];
  anki_decks: string[];
  total_notes: number;
  notes_with_progress: number;
  samples: AnkiSample[];
  suggested_deck_name: string;
}

export interface AnkiCommitRequest {
  import_id: string;
  deck_name: string;
  language: Language;
  note_type: string;
  word_field: string;
  word_extract: "whole" | "before_separator";
  prompt_field?: string | null;
  meaning_field?: string | null;
  examples_field?: string | null;
  import_progress: boolean;
  on_duplicate: "skip" | "overwrite";
}

export interface AnkiCommitResponse {
  deck_id: number;
  deck_name: string;
  imported: number;
  updated: number;
  skipped: number;
}

export interface WordUpdate {
  word?: string;
  deck_id?: number;
  prompt?: string | null;
  pos?: string | null;
  translation?: string | null;
  definitions?: string[];
  examples?: string[];
  collocations?: string[];
  gender?: string | null;
  plural_form?: string | null;
  case_notes?: string | null;
  mnemonic?: string | null;
}
