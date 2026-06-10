"""LLM access layer with a deterministic offline fallback.

The platform must run with or without LLM credentials. When a provider key is
present we call it; otherwise ``available`` is ``False`` and callers fall back to
the deterministic template engine in :mod:`app.generation`.

Supported providers:
    * ``openai``    — the OpenAI SDK directly.
    * ``anthropic`` — the Anthropic SDK directly.
    * ``litellm``   — any OpenAI-compatible endpoint, including a LiteLLM
      proxy/gateway via ``LITELLM_BASE_URL``. This is the recommended option for
      enterprise deployments that centralise model access behind one gateway.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from .config import settings

logger = logging.getLogger("testgen.llm")


class LLMClient:
    """Thin wrapper over OpenAI / Anthropic / LiteLLM with graceful degradation."""

    def __init__(self, model: Optional[str] = None):
        self.provider: Optional[str] = None
        self.model = model
        self._client: Any = None
        # LiteLLM routing config (module-level call, no persistent client).
        self._api_base: Optional[str] = None
        self._api_key: Optional[str] = None
        self._init_provider(model)

    def _resolve_provider(self) -> str:
        """Resolve ``auto`` to a concrete provider based on configured creds."""
        provider = settings.LLM_PROVIDER
        if provider != "auto":
            return provider
        # Prefer an explicit LiteLLM gateway, then OpenAI, then Anthropic.
        if settings.LITELLM_BASE_URL or settings.LITELLM_API_KEY:
            return "litellm"
        if settings.OPENAI_API_KEY:
            return "openai"
        if settings.ANTHROPIC_API_KEY:
            return "anthropic"
        return "none"

    def _init_provider(self, model: Optional[str]) -> None:
        provider = self._resolve_provider()

        if provider == "openai" and settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.provider = "openai"
                self.model = model or settings.OPENAI_MODEL
            except Exception as exc:  # pragma: no cover - import/credential issues
                logger.warning("OpenAI unavailable, using fallback: %s", exc)
        elif provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            try:
                from anthropic import Anthropic

                self._client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                self.provider = "anthropic"
                self.model = model or settings.ANTHROPIC_MODEL
            except Exception as exc:  # pragma: no cover
                logger.warning("Anthropic unavailable, using fallback: %s", exc)
        elif provider == "litellm":
            try:
                import litellm  # noqa: F401

                self._client = litellm
                self.provider = "litellm"
                self.model = model or settings.LITELLM_MODEL
                self._api_base = settings.LITELLM_BASE_URL
                # Fall back to the standard OpenAI key when no gateway key is set,
                # so ``litellm`` works against OpenAI directly too.
                self._api_key = settings.LITELLM_API_KEY or settings.OPENAI_API_KEY
            except Exception as exc:  # pragma: no cover
                logger.warning("LiteLLM unavailable, using fallback: %s", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1200) -> str:
        if not self.available:
            raise RuntimeError("No LLM provider configured")
        system = system or "You are an expert QA engineer that writes precise BDD test cases."
        if self.provider == "openai":
            return self._complete_openai(prompt, system, max_tokens)
        if self.provider == "anthropic":
            return self._complete_anthropic(prompt, system, max_tokens)
        if self.provider == "litellm":
            return self._complete_litellm(prompt, system, max_tokens)
        raise RuntimeError(f"Unknown provider: {self.provider!r}")

    # -- provider-specific calls -------------------------------------------- #
    def _complete_openai(self, prompt: str, system: str, max_tokens: int) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    def _complete_anthropic(self, prompt: str, system: str, max_tokens: int) -> str:
        resp = self._client.messages.create(
            model=self.model,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=max_tokens,
        )
        return "".join(block.text for block in resp.content if block.type == "text").strip()

    def _complete_litellm(self, prompt: str, system: str, max_tokens: int) -> str:
        # When routing via a custom proxy, LiteLLM needs an ``openai/`` prefix to
        # select the OpenAI-compatible path; skip if a prefix is already present.
        model = self.model
        if self._api_base and "/" not in model:
            model = f"openai/{model}"
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens,
        }
        if self._api_base:
            kwargs["api_base"] = self._api_base
        if self._api_key:
            kwargs["api_key"] = self._api_key
        resp = self._client.completion(**kwargs)
        return (resp.choices[0].message.content or "").strip()

    def complete_json(
        self, prompt: str, system: str = "", max_tokens: int = 1200
    ) -> Optional[Dict[str, Any]]:
        """Call the model and best-effort parse a JSON object from the reply."""
        try:
            raw = self.complete(prompt, system=system, max_tokens=max_tokens)
        except Exception as exc:
            logger.warning("LLM completion failed: %s", exc)
            return None
        return _extract_json(raw)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    # Strip ```json fences if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None
