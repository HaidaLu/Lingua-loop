from __future__ import annotations

import logging

from app.config import settings
from app.llm.base import CardGenerator

logger = logging.getLogger(__name__)

_generator: CardGenerator | None = None


def get_generator() -> CardGenerator:
    global _generator
    if _generator is not None:
        return _generator

    provider = settings.effective_provider
    if settings.llm_provider != provider:
        logger.warning(
            "LLM_PROVIDER=%s but no matching API key configured; falling back to the mock generator.",
            settings.llm_provider,
        )

    if provider == "claude":
        from app.llm.claude import ClaudeCardGenerator

        _generator = ClaudeCardGenerator()
    elif provider == "openai":
        from app.llm.openai_compat import OpenAICompatCardGenerator

        _generator = OpenAICompatCardGenerator()
    else:
        from app.llm.mock import MockCardGenerator

        _generator = MockCardGenerator()

    logger.info("card generator: %s", _generator.name)
    return _generator
