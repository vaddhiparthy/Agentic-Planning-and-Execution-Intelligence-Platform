from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from overthinker.core.config import OverthinkerConfig, load_config
from overthinker.core.paths import DEFAULT_PROMPTS_DIR, PROMPT_OVERRIDE_DIR


PROMPT_FILES = {
    "planner": "system_planner.txt",
    "persona_general": "persona_general.txt",
}


@dataclass
class LLMCallResult:
    content: str
    provider: str
    configured_model: str
    effective_model: str


def _read_prompt(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_system_prompts() -> dict[str, str]:
    prompts: dict[str, str] = {}
    for key, filename in PROMPT_FILES.items():
        override = _read_prompt(PROMPT_OVERRIDE_DIR / filename)
        default = _read_prompt(DEFAULT_PROMPTS_DIR / filename)
        prompts[key] = override or default
    return prompts


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
