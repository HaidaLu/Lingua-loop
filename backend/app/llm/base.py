from __future__ import annotations

from typing import Protocol

from app.schemas import LLMCard


class CardGenerator(Protocol):
    name: str

    def generate(self, word: str, language: str, context: str | None = None) -> LLMCard:
        """Given a word + language (+ optional context sentence), return a structured card."""
        ...
