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
    LLM_PROVIDER: str = os.environ.get("TESTGEN_LLM_PROVIDER", "auto")  # auto|openai|anthropic|none
    OPENAI_API_KEY: str | None = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.environ.get("TESTGEN_OPENAI_MODEL", "gpt-4o")
    ANTHROPIC_API_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = os.environ.get("TESTGEN_ANTHROPIC_MODEL", "claude-3-7-sonnet-20250219")
    LLM_TEMPERATURE: float = float(os.environ.get("TESTGEN_LLM_TEMPERATURE", "0.7"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
