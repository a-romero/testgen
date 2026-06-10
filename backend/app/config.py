"""Runtime configuration for the TestGen backend.

All values can be overridden via environment variables so the same image runs
locally (no API keys, deterministic fallback generation) or against a real LLM
provider in an enterprise deployment.
"""

import os
from functools import lru_cache


class Settings:
    # API auth — a single shared key is enough for an internal QA tool. Replace
    # with SSO / per-user keys in production (see HLR2 access controls).
    API_KEY: str = os.environ.get("TESTGEN_API_KEY", "changeme-local-dev")

    # Where SQLite databases live. Defaults to backend/data.
    DB_DIR: str = os.environ.get(
        "TESTGEN_DB_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")),
    )

    # LLM configuration. If no provider/key is configured the generator falls
    # back to a deterministic template engine, so the platform always runs.
    # Providers: auto | openai | anthropic | litellm | none
    LLM_PROVIDER: str = os.environ.get("TESTGEN_LLM_PROVIDER", "auto")
    OPENAI_API_KEY: str | None = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.environ.get("TESTGEN_OPENAI_MODEL", "gpt-4o")
    ANTHROPIC_API_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = os.environ.get("TESTGEN_ANTHROPIC_MODEL", "claude-3-7-sonnet-20250219")
    # LiteLLM gives access to any OpenAI-compatible endpoint (incl. a LiteLLM
    # proxy/gateway). When ``LITELLM_BASE_URL`` is set the model is routed through
    # the OpenAI-compatible path with an ``openai/`` prefix when needed.
    LITELLM_MODEL: str = os.environ.get("TESTGEN_LITELLM_MODEL", "gpt-4o")
    LITELLM_BASE_URL: str | None = os.environ.get("LITELLM_BASE_URL")
    LITELLM_API_KEY: str | None = os.environ.get("LITELLM_API_KEY")
    LLM_TEMPERATURE: float = float(os.environ.get("TESTGEN_LLM_TEMPERATURE", "0.7"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
