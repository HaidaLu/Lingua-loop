from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings
from app.schemas import LLMCard

_SYSTEM = """\
You build vocabulary flashcards for someone learning English and German whose native language is Chinese.

The user gives you a SEARCH TEXT and a TARGET LANGUAGE (english or german). The search text may be:
  - the target-language word itself (possibly inflected or slightly misspelled), or
  - a word in another language — usually Chinese, sometimes English when the target is German.

Your job:
1. Resolve the search text to the canonical dictionary form in the TARGET LANGUAGE ("headword"):
   verbs → infinitive; nouns → nominative singular (German: keep the article, e.g. "die Sorge");
   adjectives → positive form. If the search text is Chinese/English, translate it to the single most
   common target-language word for that meaning (use the context sentence if given to disambiguate).
2. Set "query_language": "target" if the search text was already the target language, else "other".
3. Write EVERYTHING ELSE IN ENGLISH — definitions, examples' explanations are not needed, collocations,
   case_notes, mnemonic. Never explain a German word in German. "translation" = one concise English gloss.
4. "examples": 2-3 natural sentences IN THE TARGET LANGUAGE using the headword.

Output ONE JSON object, no markdown fences, no extra text:
{
  "headword": string,            // canonical form in the target language
  "query_language": "target" | "other",
  "pos": string|null,            // part of speech, in English (e.g. "noun", "verb", "adjective")
  "translation": string|null,    // one concise English gloss
  "definitions": string[],       // 1-3 English definitions
  "examples": string[],          // 2-3 target-language sentences; if context given, at least one fits it
  "collocations": string[],      // 2-5 common target-language collocations / set phrases
  "gender": "der"|"die"|"das"|null,
  "plural_form": string|null,
  "case_notes": string|null,     // English note on case government
  "mnemonic": string|null        // an English memory hook
}

Rules:
- English headword: gender / plural_form / case_notes must be null.
- German noun: gender required (der/die/das); give the plural; note common case government in English.
- German verb/adjective/adverb: gender null; state the part of speech in pos.
"""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -3]
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    return t.strip()


class OpenAICompatCardGenerator:
    """Card generator for any OpenAI-compatible endpoint — DashScope/Qwen, OpenAI, etc."""

    name = "openai"

    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=settings.resolved_openai_key,
            base_url=settings.resolved_openai_base_url,
        )
        self._model = settings.openai_model

    def _call(self, messages: list[dict], *, json_mode: bool) -> str:
        kwargs: dict = {"model": self._model, "messages": messages, "temperature": 0.3}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def generate(self, word: str, language: str, context: str | None = None) -> LLMCard:
        lang_label = "english" if language == "en" else "german"
        user_lines = [f"TARGET LANGUAGE: {lang_label}", f"SEARCH TEXT: {word}"]
        if context:
            user_lines.append(f"CONTEXT SENTENCE: {context}")
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": "\n".join(user_lines)},
        ]

        try:
            raw = self._call(messages, json_mode=True)
        except Exception:
            raw = self._call(messages, json_mode=False)

        data = json.loads(_strip_fences(raw))
        card = LLMCard.model_validate(data)
        if language == "en":
            card.gender = None
            card.plural_form = None
            card.case_notes = None
        return card
