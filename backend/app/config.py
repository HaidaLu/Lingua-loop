from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "claude" | "openai" (any OpenAI-compatible endpoint incl. DashScope/Qwen) | "mock"
    llm_provider: str = "openai"

    # --- Anthropic ---
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5"

    # --- OpenAI-compatible (DashScope / Qwen / OpenAI / ...) ---
    openai_api_key: str | None = None
    dashscope_api_key: str | None = None
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_base_url: str | None = None
    openai_model: str = "qwen3-max"

    # --- auth (single-user login gate) ---
    auth_secret: str = "dev-insecure-secret-change-me-in-production-32b+"  # set a random value in production
    auth_token_ttl_hours: int = 24 * 30

    # --- infra ---
    database_url: str = "sqlite:///./language_learning.db"
    media_dir: str = "./media"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_openai_key(self) -> str | None:
        return self.openai_api_key or self.dashscope_api_key

    @property
    def resolved_openai_base_url(self) -> str:
        return self.dashscope_base_url or self.openai_base_url

    @property
    def effective_provider(self) -> str:
        """If a keyed provider is set but its API key is missing, fall back to mock so endpoints still work."""
        p = self.llm_provider
        if p == "claude" and not self.anthropic_api_key:
            return "mock"
        if p == "openai" and not self.resolved_openai_key:
            return "mock"
        return p


settings = Settings()
