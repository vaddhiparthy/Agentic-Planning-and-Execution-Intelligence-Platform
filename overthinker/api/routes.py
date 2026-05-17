from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from overthinker.core.config import OverthinkerConfig, load_config, save_config
from overthinker.core.models import GoalItem, Scope
from overthinker.core.paths import CONFIG_FILE, DATABASE_FILE, PROMPT_OVERRIDE_DIR, UI_DIR
from overthinker.demo_content import DEMO_RUNS, render_demo_page
from overthinker.services.evals import eval_summary, run_static_eval_suite
from overthinker.services.guardrails import guardrail_summary
from overthinker.services.llm import choose_preferred_ollama_model, fetch_ollama_models
from overthinker.services.model_router import router_summary
from overthinker.services.planner import run_iteration
from overthinker.services.prompt_registry import prompt_registry_summary
from overthinker.services.scheduler import OverthinkerScheduler
from overthinker.storage.factory import create_repository

router = APIRouter()


class GoalDocumentPayload(BaseModel):
    items: list[GoalItem] = Field(default_factory=list)
    notes: str = ""


class GoalMarkdownImportPayload(BaseModel):
    text: str


class RunPayload(BaseModel):
    scope: Scope


class FeedbackPayload(BaseModel):
    scope: Scope
    text: str


class ConfigPayload(BaseModel):
    model: dict
    schedule: dict
    runtime: dict
    storage: dict


class EvalRunPayload(BaseModel):
    suite: str = "planning_basic"


def repository_from(request: Request):
    return request.app.state.repository


def scheduler_from(request: Request):
    return request.app.state.scheduler


async def build_runtime_diagnostics(request: Request) -> dict:
    cfg = load_config()
    repository = repository_from(request)
    scheduler = scheduler_from(request).snapshot()

    ollama_available_models: list[str] = []
    ollama_effective_model: str | None = None
    ollama_error: str | None = None
    ollama_configured_model_available = False
    provider_ready = bool(os.getenv(cfg.model.api_key_env, "").strip())
    provider_reason = None if provider_ready else f"Missing API key in '{cfg.model.api_key_env}'."

    if cfg.model.provider == "ollama":
        provider_ready = False
        provider_reason = "Ollama diagnostics not loaded."
        try:
            ollama_available_models = await fetch_ollama_models(
                base_url=cfg.model.api_base or "http://127.0.0.1:11434",
                timeout_seconds=10,
            )
            ollama_effective_model = choose_preferred_ollama_model(
                ollama_available_models, cfg.model.model_name
            )
            ollama_configured_model_available = cfg.model.model_name in ollama_available_models
            provider_ready = ollama_configured_model_available
            if not ollama_configured_model_available and ollama_effective_model:
                provider_reason = (
                    f"Configured model '{cfg.model.model_name}' is not installed. "
                    f"Suggested model: '{ollama_effective_model}'."
                )
            else:
                provider_reason = None
        except ValueError as exc:
            ollama_error = str(exc)
            provider_reason = ollama_error

    scope_readiness = []
    for scope in Scope:
        goal_document = repository.get_goal_document(scope)
        active_goal_count = sum(1 for item in goal_document.items if item.active and item.title.strip())
        can_run = provider_ready and active_goal_count > 0
        reasons: list[str] = []
        if active_goal_count == 0:
            reasons.append("No active goals saved for this scope.")
        if not provider_ready and provider_reason:
            reasons.append(provider_reason)
        scope_readiness.append(
            {
                "scope": scope.value,
                "active_goal_count": active_goal_count,
                "feedback_count": len(repository.list_feedback(scope, limit=100)),
                "run_count_today": repository.count_runs_today(scope),
                "current_run_id": (
                    repository.get_current_run(scope).run_id
                    if repository.get_current_run(scope) is not None
                    else None
                ),
                "can_run": can_run,
                "reasons": reasons,
            }
        )

    return {
        "config": cfg.model_dump(mode="json"),
        "scheduler": scheduler.model_dump(mode="json"),
        "paths": {
            "database": (
                str(DATABASE_FILE)
                if cfg.storage.backend.lower() == "sqlite"
                else f"postgresql://{cfg.storage.postgres_user}@{cfg.storage.postgres_host}:{cfg.storage.postgres_port}/{cfg.storage.postgres_database}"
            ),
            "config": str(CONFIG_FILE),
            "prompt_overrides": str(PROMPT_OVERRIDE_DIR),
        },
        "diagnostics": {
            "storage_backend": cfg.storage.backend,
            "storage_schema": cfg.storage.postgres_schema if cfg.storage.backend.lower() == "postgres" else None,
            "storage_table_prefix": cfg.storage.postgres_table_prefix if cfg.storage.backend.lower() == "postgres" else None,
            "provider": cfg.model.provider,
            "provider_ready": provider_ready,
            "provider_reason": provider_reason,
            "openai_key_present": bool(os.getenv(cfg.model.api_key_env, "").strip()),
            "ollama_available_models": ollama_available_models,
            "ollama_effective_model": ollama_effective_model,
            "ollama_configured_model_available": ollama_configured_model_available,
            "ollama_error": ollama_error,
            "scope_readiness": scope_readiness,
        },
    }


@router.get("/")
async def root():
    return HTMLResponse(render_demo_page())


@router.get("/demo")
async def demo():
    return HTMLResponse(render_demo_page())


@router.get("/api/demo/frozen-runs")
async def frozen_demo_runs():
    return {"runs": DEMO_RUNS}


@router.get("/api/operations/evidence")
async def operations_evidence():
    return {
        "model_router": router_summary(),
        "prompt_registry": prompt_registry_summary(),
        "guardrails": guardrail_summary(),
        "evaluation_harness": eval_summary(),
    }


@router.post("/api/evals/run")
async def run_eval_suite(payload: EvalRunPayload):
    return {"ok": True, **run_static_eval_suite(payload.suite)}


@router.get("/api/health")
async def health(request: Request):
    payload = await build_runtime_diagnostics(request)
    return {
        "status": "ok",
        "database_path": str(DATABASE_FILE),
        "config_path": str(CONFIG_FILE),
        "prompt_override_dir": str(PROMPT_OVERRIDE_DIR),
        "provider_ready": payload["diagnostics"]["provider_ready"],
        "provider_reason": payload["diagnostics"]["provider_reason"],
        "scheduler": payload["scheduler"],
        "scope_readiness": payload["diagnostics"]["scope_readiness"],
    }


@router.get("/api/goals/{scope}")
async def get_goals(scope: Scope, request: Request):
    document = repository_from(request).get_goal_document(scope)
    return document.model_dump(mode="json")


@router.put("/api/goals/{scope}")
async def set_goals(scope: Scope, payload: GoalDocumentPayload, request: Request):
    repository = repository_from(request)
    cleaned_items = []
    for index, item in enumerate(payload.items):
        if not item.title.strip() and not item.details.strip():
            continue
        cleaned_items.append(item.model_copy(update={"order": index}))
    document = repository.save_goal_document(scope, cleaned_items, payload.notes)
    return {"ok": True, "document": document.model_dump(mode="json")}


@router.post("/api/goals/{scope}/import-markdown")
async def import_goals_markdown(scope: Scope, payload: GoalMarkdownImportPayload, request: Request):
    items = []
    notes = []
    for raw_line in payload.text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ")):
            items.append(GoalItem(title=stripped[2:].strip(), order=len(items)))
        else:
            notes.append(stripped)
    document = repository_from(request).save_goal_document(scope, items, "\n".join(notes))
    return {"ok": True, "document": document.model_dump(mode="json")}


@router.get("/api/feedback/{scope}")
async def list_feedback(scope: Scope, request: Request):
    entries = repository_from(request).list_feedback(scope)
    return {"scope": scope.value, "entries": [entry.model_dump(mode="json") for entry in entries]}


@router.post("/api/feedback")
async def add_feedback(payload: FeedbackPayload, request: Request):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Feedback text is required.")
    entry = repository_from(request).add_feedback(payload.scope, text)
    return {"ok": True, "entry": entry.model_dump(mode="json")}


@router.get("/api/runs/{scope}/current")
async def current_run(scope: Scope, request: Request):
    current = repository_from(request).get_current_run(scope)
    return {"scope": scope.value, "current": current.model_dump(mode="json") if current else None}


@router.get("/api/runs/{scope}/history")
async def run_history(scope: Scope, request: Request, limit: int = 20):
    runs = repository_from(request).list_runs(scope, limit=max(1, min(limit, 100)))
    return {"scope": scope.value, "runs": [run.model_dump(mode="json") for run in runs]}


@router.post("/api/runs")
async def run_now(payload: RunPayload, request: Request):
    try:
        result = await run_iteration(payload.scope, load_config(), repository_from(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.post("/api/runs/{scope}/archive")
async def archive_run(scope: Scope, request: Request):
    archived = repository_from(request).archive_current_run(scope)
    if archived is None:
        raise HTTPException(status_code=400, detail="No current run to archive.")
    return {"ok": True, "run": archived.model_dump(mode="json")}


@router.get("/api/config")
async def get_config():
    return load_config().model_dump(mode="json")


@router.post("/api/config")
async def update_config(payload: ConfigPayload, request: Request):
    current = load_config()
    new_cfg = OverthinkerConfig(
        model=current.model.__class__(**payload.model),
        schedule=current.schedule.__class__(**payload.schedule),
        runtime=current.runtime.__class__(**payload.runtime),
        storage=current.storage.__class__(**payload.storage),
    )
    if new_cfg.model.provider.lower() == "ollama":
        try:
            models = await fetch_ollama_models(
                base_url=new_cfg.model.api_base or "http://127.0.0.1:11434",
                timeout_seconds=min(new_cfg.model.request_timeout_seconds, 15),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if new_cfg.model.model_name not in models:
            suggested = choose_preferred_ollama_model(models, new_cfg.model.model_name)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Configured Ollama model '{new_cfg.model.model_name}' is not installed. "
                    f"Use '{suggested}' or install the requested model first."
                ),
            )
    current_storage = current.storage.model_dump(mode="json")
    new_storage = new_cfg.storage.model_dump(mode="json")
    staged_repository = None

    if current_storage != new_storage:
        try:
            staged_repository = create_repository(new_cfg)
            staged_repository.initialize()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Storage configuration failed: {exc}") from exc

    save_config(new_cfg)

    if current_storage != new_storage:
        old_repository = repository_from(request)
        snapshot = old_repository.export_storage_snapshot()
        new_repository = staged_repository or create_repository(new_cfg)
        new_repository.import_storage_snapshot(snapshot)

        current_scheduler = scheduler_from(request)
        await current_scheduler.shutdown()
        new_scheduler = OverthinkerScheduler(new_repository)
        request.app.state.repository = new_repository
        request.app.state.scheduler = new_scheduler
        await new_scheduler.start()
    else:
        await scheduler_from(request).reload()

    restart_required = [
        field
        for field in ("host", "port", "cors_origins")
        if getattr(current.runtime, field) != getattr(new_cfg.runtime, field)
    ]
    if current_storage != new_storage:
        restart_required.append("storage")
    return {
        "ok": True,
        "config": new_cfg.model_dump(mode="json"),
        "restart_required_fields": restart_required,
    }


@router.get("/api/control-panel")
async def control_panel(request: Request):
    return await build_runtime_diagnostics(request)


@router.get("/api/providers/ollama/models")
async def ollama_models():
    cfg = load_config()
    try:
        models = await fetch_ollama_models(
            base_url=cfg.model.api_base or "http://127.0.0.1:11434",
            timeout_seconds=10,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    effective_model = choose_preferred_ollama_model(models, cfg.model.model_name) if models else None
    return {"models": models, "effective_model": effective_model}
