from __future__ import annotations

from app.schemas import LLMCard

# A few common German noun articles so mock output looks plausible; otherwise guess by suffix.
_DE_GENDER = {
    "haus": "das", "frau": "die", "mann": "der", "kind": "das", "auto": "das",
    "buch": "das", "tisch": "der", "tür": "die", "stadt": "die", "land": "das",
    "arbeit": "die", "weg": "der", "zeit": "die", "tag": "der", "nacht": "die",
    "sorge": "die", "wohnung": "die", "verabredung": "die",
}


def _guess_de_gender(word: str) -> str | None:
    w = word.strip().lower()
    if w in _DE_GENDER:
        return _DE_GENDER[w]
    if w.endswith(("ung", "heit", "keit", "schaft", "tion", "ei", "ie")):
        return "die"
    if w.endswith(("chen", "lein", "ment", "um")):
        return "das"
    if w.endswith(("er", "ling", "ismus")):
        return "der"
    if word[:1].isupper():  # looks like a noun but no guess — placeholder
        return "die"
    return None


def _is_target_language(query: str, language: str) -> bool:
    # crude: any CJK char (U+4E00..U+9FFF) => not the target language
    return not any(0x4E00 <= ord(ch) <= 0x9FFF for ch in query)


class MockCardGenerator:
    name = "mock"

    def generate(self, word: str, language: str, context: str | None = None) -> LLMCard:
        q = word.strip()
        in_target = _is_target_language(q, language)
        # if the query isn't the target language, "resolve" to a placeholder headword
        headword = q if in_target else (f"Wort<{q}>" if language == "de" else f"word<{q}>")
        query_language = "target" if in_target else "other"

        if language == "de":
            is_noun = headword[:1].isupper()
            gender = _guess_de_gender(headword) if is_noun else None
            return LLMCard(
                headword=headword,
                query_language=query_language,
                pos="noun" if is_noun else "verb/adjective (mock)",
                translation=f"[mock] English gloss for '{headword}'",
                definitions=[f"[mock] English definition of '{headword}'", "[mock] a secondary sense"],
                examples=[
                    f"Ich sehe {('den ' + headword) if is_noun else headword} jeden Tag.",
                    (context or f"Das ist ein Beispiel mit „{headword}“."),
                ],
                collocations=[f"{headword} haben", f"mit {headword}", f"{headword} machen"],
                gender=gender,
                plural_form=(f"{headword}e" if is_noun else None),
                case_notes=("often takes the accusative" if is_noun else "verb: often with dative"),
                mnemonic=f"[mock] tie '{headword}' to a vivid mental image.",
            )
        return LLMCard(
            headword=headword,
            query_language=query_language,
            pos="noun/verb (mock)",
            translation=f"[mock] English gloss for '{headword}'",
            definitions=[f"[mock] the meaning of '{headword}'", f"[mock] a secondary sense of '{headword}'"],
            examples=[
                f"She used the word '{headword}' in the meeting.",
                (context or f"This is an example sentence containing '{headword}'."),
            ],
            collocations=[f"a strong {headword}", f"to {headword} something", f"{headword} rate"],
            gender=None,
            plural_form=None,
            case_notes=None,
            mnemonic=f"[mock] mnemonic: link '{headword}' to a vivid mental image.",
        )
