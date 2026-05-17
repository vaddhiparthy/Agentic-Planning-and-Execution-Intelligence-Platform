from __future__ import annotations

from typing import Any

from overthinker.core.config import OverthinkerConfig, load_config
from overthinker.core.models import Scope
from overthinker.services.guardrails import check_input, check_output
from overthinker.services.llm import call_llm
from overthinker.services.prompt_registry import render_prompt


def _format_goals(document) -> str:
    lines: list[str] = []
    active_items = [item for item in document.items if item.active and item.title.strip()]
    if active_items:
        lines.append("Active goals:")
        for item in sorted(active_items, key=lambda entry: entry.order):
            lines.append(f"- [{item.priority}/5] {item.title.strip()}")
            if item.details.strip():
                lines.append(f"  details: {item.details.strip()}")
    if document.notes.strip():
        lines.append("")
        lines.append("Context notes:")
        lines.append(document.notes.strip())
    return "\n".join(lines).strip()


def _format_feedback(entries) -> str:
    if not entries:
        return "(no feedback yet)"
    chunks = []
    for entry in reversed(entries):
        chunks.append(f"[{entry.created_at}] {entry.text.strip()}")
    return "\n".join(chunks)


async def run_iteration(
    scope: Scope,
    cfg: OverthinkerConfig | None = None,
    repository=None,
    *,
    trigger: str = "manual",
) -> dict[str, Any]:
    cfg = cfg or load_config()
    from overthinker.storage.factory import create_repository

    repository = repository or create_repository(cfg)
    goals = repository.get_goal_document(scope)
    goals_text = _format_goals(goals)
    if not goals_text:
        raise ValueError(f"No structured goals found for scope '{scope.value}'.")

    if repository.count_runs_today(scope) >= cfg.schedule.rate_limit_per_day:
        raise ValueError(
            f"Rate limit reached for '{scope.value}' ({cfg.schedule.rate_limit_per_day} runs today)."
        )

    current = repository.get_current_run(scope)
    feedback = repository.list_feedback(scope, limit=12)

    system_prompt = render_prompt("planner_system")
    persona_prompt = render_prompt("planner_persona")
    user_prompt = render_prompt(
        "planner_user_payload",
        {
            "scope": scope.value,
            "goals": goals_text,
            "current_plan": current.plan_markdown if current else "(none yet)",
            "feedback": _format_feedback(feedback),
        },
    )

    check_input(user_prompt.content)

    messages = [
        {
            "role": "system",
            "content": system_prompt.content,
        },
        {
            "role": "system",
            "content": persona_prompt.content,
        },
        {"role": "user", "content": user_prompt.content},
    ]

    reply = await call_llm(messages, cfg)
    check_output(reply.content)
    record = repository.create_run(
        scope,
        reply.content,
        trigger=trigger,
        provider=reply.provider,
        configured_model=reply.configured_model,
        effective_model=reply.effective_model,
    )
    return {
        "scope": record.scope.value,
        "run_id": record.run_id,
        "ts": record.created_at,
        "plan_markdown": record.plan_markdown,
        "summary": record.summary,
        "provider": record.provider,
        "configured_model": record.configured_model,
        "effective_model": record.effective_model,
    }
