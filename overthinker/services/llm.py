from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from overthinker.core.config import OverthinkerConfig


@dataclass
class LLMCallResult:
    content: str
    provider: str
    configured_model: str
    effective_model: str


async def fetch_ollama_models(
    base_url: str = "http://127.0.0.1:11434", timeout_seconds: int = 10
) -> list[str]:
    base = base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(f"{base}/api/tags")
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Ollama is unavailable: {exc}") from exc

    payload = response.json()
    return [item.get("name") for item in payload.get("models", []) if item.get("name")]


def choose_preferred_ollama_model(available_models: list[str], configured_model: str) -> str:
    normalized = [model for model in available_models if model]
    if not normalized:
        raise ValueError("No Ollama models are installed locally.")
    if configured_model and configured_model in normalized:
        return configured_model

    preferred_prefixes = (
        "qwen2.5",
        "qwen3",
        "llama3.1",
        "llama3",
        "glm-4.7",
        "llama3.2",
    )
    for prefix in preferred_prefixes:
        for model in normalized:
            if model.startswith(prefix):
                return model
    return normalized[0]


async def call_llm(
    messages: list[dict[str, Any]], cfg: OverthinkerConfig | None = None
) -> LLMCallResult:
    from overthinker.services.model_router import route_llm_call

    return await route_llm_call(messages, cfg)
