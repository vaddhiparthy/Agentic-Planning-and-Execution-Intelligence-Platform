from __future__ import annotations

import os
import time
from dataclasses import asdict
from typing import Any

import httpx

from overthinker.core.config import OverthinkerConfig, load_config
from overthinker.core.paths import LLM_CALL_LOG_FILE
from overthinker.services.artifacts import append_jsonl, new_artifact_id, read_jsonl, utc_now_iso
from overthinker.services.llm import LLMCallResult, choose_preferred_ollama_model, fetch_ollama_models


def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    text = "\n".join(str(message.get("content", "")) for message in messages)
    return max(1, len(text) // 4)


def _capture(payload: dict[str, Any]) -> None:
    append_jsonl(LLM_CALL_LOG_FILE, payload)


async def route_llm_call(
    messages: list[dict[str, Any]],
    cfg: OverthinkerConfig | None = None,
    *,
    request_id: str | None = None,
    prompt_versions: dict[str, str] | None = None,
) -> LLMCallResult:
    cfg = cfg or load_config()
    request_id = request_id or new_artifact_id("llm")
    model_cfg = cfg.model
    started = time.perf_counter()
    prompt_tokens = _estimate_tokens(messages)
    status = "success"
    error = None
    result: LLMCallResult | None = None

    try:
        timeout = httpx.Timeout(model_cfg.request_timeout_seconds)
        if model_cfg.provider.lower() == "ollama":
            result = await _call_ollama(messages, cfg, timeout)
        else:
            result = await _call_openai_compatible(messages, cfg, timeout)
        return result
    except Exception as exc:
        status = "failed"
        error = str(exc)
        raise
    finally:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        completion_tokens = len((result.content if result else "") or "") // 4 if result else 0
        _capture(
            {
                "request_id": request_id,
                "created_at": utc_now_iso(),
                "provider": result.provider if result else model_cfg.provider,
                "configured_model": result.configured_model if result else model_cfg.model_name,
                "effective_model": result.effective_model if result else None,
                "status": status,
                "latency_ms": elapsed_ms,
                "prompt_tokens_estimate": prompt_tokens,
                "completion_tokens_estimate": completion_tokens,
                "cost_usd_estimate": 0.0,
                "prompt_versions": prompt_versions or {},
                "error": error,
            }
        )


async def _call_ollama(
    messages: list[dict[str, Any]], cfg: OverthinkerConfig, timeout: httpx.Timeout
) -> LLMCallResult:
    model_cfg = cfg.model
    base = (model_cfg.api_base or "http://127.0.0.1:11434").rstrip("/")
    effective_model = model_cfg.model_name
    try:
        available_models = await fetch_ollama_models(
            base_url=base,
            timeout_seconds=model_cfg.request_timeout_seconds,
        )
        if effective_model not in available_models:
            suggested_model = choose_preferred_ollama_model(available_models, model_cfg.model_name)
            raise ValueError(
                f"Configured Ollama model '{effective_model}' is not installed. Suggested model: '{suggested_model}'."
            )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base}/api/chat",
                json={"model": effective_model, "messages": messages, "stream": False},
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Ollama request failed: {exc}") from exc
    data = response.json()
    return LLMCallResult(
        content=data.get("message", {}).get("content", "").strip(),
        provider=model_cfg.provider,
        configured_model=model_cfg.model_name,
        effective_model=effective_model,
    )


async def _call_openai_compatible(
    messages: list[dict[str, Any]], cfg: OverthinkerConfig, timeout: httpx.Timeout
) -> LLMCallResult:
    model_cfg = cfg.model
    base = (model_cfg.api_base or "https://api.openai.com").rstrip("/")
    api_key = os.getenv(model_cfg.api_key_env, "").strip()
    if not api_key:
        raise ValueError(f"Missing API key in environment variable '{model_cfg.api_key_env}'.")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model_cfg.model_name,
                    "temperature": model_cfg.temperature,
                    "max_tokens": model_cfg.max_tokens,
                    "messages": messages,
                },
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Model request failed: {exc}") from exc
    data = response.json()
    return LLMCallResult(
        content=data["choices"][0]["message"]["content"].strip(),
        provider=model_cfg.provider,
        configured_model=model_cfg.model_name,
        effective_model=data.get("model", model_cfg.model_name),
    )


def router_summary(limit: int = 100) -> dict:
    rows = read_jsonl(LLM_CALL_LOG_FILE, limit=limit)
    success = [row for row in rows if row.get("status") == "success"]
    failed = [row for row in rows if row.get("status") == "failed"]
    avg_latency = (
        round(sum(float(row.get("latency_ms") or 0) for row in rows) / len(rows), 2)
        if rows
        else None
    )
    return {
        "artifact_path": str(LLM_CALL_LOG_FILE),
        "call_count": len(rows),
        "success_count": len(success),
        "failure_count": len(failed),
        "average_latency_ms": avg_latency,
        "recent_calls": rows[-20:],
    }
