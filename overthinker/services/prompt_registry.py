from __future__ import annotations

from dataclasses import dataclass
from string import Template

from overthinker.core.paths import DEFAULT_PROMPTS_DIR, PROMPT_OVERRIDE_DIR, PROMPT_REGISTRY_FILE
from overthinker.services.artifacts import read_json, utc_now_iso, write_json


DEFAULT_PROMPTS = {
    "planner_system": {
        "version": "1.0.0",
        "status": "production",
        "purpose": "System instruction for converting scoped goals and feedback into an execution plan.",
        "template": "You are an execution planner that turns goals into practical next steps.",
        "required_variables": [],
    },
    "planner_persona": {
        "version": "1.0.0",
        "status": "production",
        "purpose": "Style and operating discipline for generated plans.",
        "template": "Be direct, organized, and operationally useful.",
        "required_variables": [],
    },
    "planner_user_payload": {
        "version": "1.0.0",
        "status": "production",
        "purpose": "Runtime user payload assembled from scope, goals, current plan, and feedback memory.",
        "template": """[GOAL_SCOPE]
$scope

[STRUCTURED_GOALS]
$goals

[CURRENT_PLAN]
$current_plan

[FEEDBACK]
$feedback

[INSTRUCTIONS]
- Produce a concrete plan that moves the scope forward.
- Keep sections concise and operational.
- Show how feedback changed the plan when feedback exists.
- Output markdown with these sections only:
  - Path to completion
  - Steps
  - Risks
  - Summary
""",
        "required_variables": ["scope", "goals", "current_plan", "feedback"],
    },
}


PROMPT_FILE_MAP = {
    "planner_system": "system_planner.txt",
    "planner_persona": "persona_general.txt",
}


@dataclass(frozen=True)
class RenderedPrompt:
    name: str
    version: str
    content: str


def _read_prompt_text(filename: str) -> str:
    override = PROMPT_OVERRIDE_DIR / filename
    default = DEFAULT_PROMPTS_DIR / filename
    if override.exists():
        return override.read_text(encoding="utf-8").strip()
    if default.exists():
        return default.read_text(encoding="utf-8").strip()
    return ""


def _seed_registry() -> dict:
    prompts = {}
    for name, payload in DEFAULT_PROMPTS.items():
        record = dict(payload)
        if name in PROMPT_FILE_MAP:
            file_text = _read_prompt_text(PROMPT_FILE_MAP[name])
            if file_text:
                record["template"] = file_text
        prompts[name] = [record | {"created_at": utc_now_iso()}]
    return {"prompts": prompts, "updated_at": utc_now_iso()}


def load_registry() -> dict:
    registry = read_json(PROMPT_REGISTRY_FILE, None)
    if registry is None:
        registry = _seed_registry()
        write_json(PROMPT_REGISTRY_FILE, registry)
    return registry


def list_prompt_versions() -> list[dict]:
    registry = load_registry()
    rows = []
    for name, versions in registry.get("prompts", {}).items():
        for version in versions:
            rows.append({"name": name, **version})
    return sorted(rows, key=lambda row: (row["name"], row["version"]))


def get_prompt(name: str, status: str = "production") -> dict:
    versions = load_registry().get("prompts", {}).get(name, [])
    for version in reversed(versions):
        if version.get("status") == status:
            return {"name": name, **version}
    raise KeyError(f"No {status} prompt found for {name}.")


def render_prompt(name: str, variables: dict | None = None) -> RenderedPrompt:
    variables = variables or {}
    prompt = get_prompt(name)
    missing = [key for key in prompt.get("required_variables", []) if key not in variables]
    if missing:
        raise ValueError(f"Prompt '{name}' missing variables: {', '.join(missing)}")
    content = Template(prompt["template"]).safe_substitute(**variables).strip()
    return RenderedPrompt(name=name, version=prompt["version"], content=content)


def prompt_registry_summary() -> dict:
    rows = list_prompt_versions()
    return {
        "artifact_path": str(PROMPT_REGISTRY_FILE),
        "prompt_count": len({row["name"] for row in rows}),
        "version_count": len(rows),
        "production_prompts": [row for row in rows if row.get("status") == "production"],
    }
