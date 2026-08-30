from __future__ import annotations

import json

import anthropic

from app.config import settings
from app.schemas import LLMCard

_SYSTEM = """\
You build vocabulary flashcards for someone learning English and German whose native language is Chinese.

The user gives you a SEARCH TEXT and a TARGET LANGUAGE (english or german). The search text may be
the target-language word itself (possibly inflected or misspelled), OR a word in another language —
usually Chinese, sometimes English when the target is German.

Your job:
1. Resolve the search text to the canonical dictionary form in the TARGET LANGUAGE ("headword"):
   verbs -> infinitive; nouns -> nominative singular (German: keep the article, e.g. "die Sorge");
   adjectives -> positive form. If the search text is Chinese/English, translate it to the single most
   common target-language word for that meaning (use the context sentence to disambiguate if given).
2. Set query_language: "target" if the search text was already the target language, otherwise "other".
3. Write everything else IN ENGLISH — definitions, collocations, case_notes, mnemonic. Never explain a
   German word in German. translation = one concise English gloss.
4. examples: 2-3 natural sentences IN THE TARGET LANGUAGE using the headword.
5. English headword -> gender / plural_form / case_notes null. German noun -> gender (der/die/das)
   required, give the plural, note common case government in English. German verb/adjective/adverb ->
   gender null, state the part of speech in pos.

Return the card by calling the save_vocab_card tool.
"""

_TOOL: anthropic.types.ToolParam = {
    "name": "save_vocab_card",
    "description": "Save the structured vocabulary card for the resolved headword.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headword": {"type": "string", "description": "canonical form in the target language"},
            "query_language": {"type": "string", "enum": ["target", "other"]},
            "pos": {"type": ["string", "null"], "description": "part of speech, in English"},
            "translation": {"type": ["string", "null"], "description": "one concise English gloss"},
            "definitions": {"type": "array", "items": {"type": "string"}},
            "examples": {"type": "array", "items": {"type": "string"}},
            "collocations": {"type": "array", "items": {"type": "string"}},
            "gender": {"type": ["string", "null"], "enum": ["der", "die", "das", None]},
            "plural_form": {"type": ["string", "null"]},
            "case_notes": {"type": ["string", "null"]},
            "mnemonic": {"type": ["string", "null"]},
        },
        "required": [
            "headword",
            "query_language",
            "pos",
            "translation",
            "definitions",
            "examples",
            "collocations",
            "gender",
            "plural_form",
            "case_notes",
            "mnemonic",
        ],
    },
}


class ClaudeCardGenerator:
    name = "claude"

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.llm_model

    def generate(self, word: str, language: str, context: str | None = None) -> LLMCard:
        lang_label = "english" if language == "en" else "german"
        user_lines = [f"TARGET LANGUAGE: {lang_label}", f"SEARCH TEXT: {word}"]
        if context:
            user_lines.append(f"CONTEXT SENTENCE: {context}")

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": "\n".join(user_lines)}],
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "save_vocab_card"},
        )

        tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise RuntimeError("Claude did not return a save_vocab_card tool call")

        data = tool_use.input
        if isinstance(data, str):
            data = json.loads(data)

        card = LLMCard.model_validate(data)
        if language == "en":
            card.gender = None
            card.plural_form = None
            card.case_notes = None
        return card
