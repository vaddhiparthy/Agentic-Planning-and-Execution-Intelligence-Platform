from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from overthinker.core.paths import GUARDRAIL_EVENT_LOG_FILE
from overthinker.services.artifacts import append_jsonl, new_artifact_id, read_jsonl, utc_now_iso


GuardrailStage = Literal["input", "output"]
GuardrailSeverity = Literal["pass", "warn", "block"]


@dataclass(frozen=True)
class GuardrailCheck:
    name: str
    stage: GuardrailStage
    severity: GuardrailSeverity
    passed: bool
    message: str


SENSITIVE_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "api_key_shape": re.compile(r"\b(?:sk-|AKIA|ASIA)[A-Za-z0-9/_+=-]{12,}\b"),
}

INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?(previous|prior) instructions", re.IGNORECASE),
    re.compile(r"reveal (your )?(system|developer) prompt", re.IGNORECASE),
    re.compile(r"bypass (the )?(rules|policy|guardrails)", re.IGNORECASE),
]


def _record(check: GuardrailCheck, request_id: str | None = None) -> None:
    append_jsonl(
        GUARDRAIL_EVENT_LOG_FILE,
        {
            "event_id": new_artifact_id("guard"),
            "request_id": request_id,
            "created_at": utc_now_iso(),
            **check.__dict__,
        },
    )


def check_input(text: str, request_id: str | None = None) -> list[GuardrailCheck]:
    checks: list[GuardrailCheck] = []
    for name, pattern in SENSITIVE_PATTERNS.items():
        matched = bool(pattern.search(text))
        checks.append(
            GuardrailCheck(
                name=f"sensitive_{name}",
                stage="input",
                severity="block" if matched else "pass",
                passed=not matched,
                message="Sensitive credential or personal-data pattern detected." if matched else "No match.",
            )
        )
    injection = any(pattern.search(text) for pattern in INJECTION_PATTERNS)
    checks.append(
        GuardrailCheck(
            name="prompt_injection_phrase",
            stage="input",
            severity="block" if injection else "pass",
            passed=not injection,
            message="Prompt-injection style instruction detected." if injection else "No match.",
        )
    )
    too_long = len(text) > 18000
    checks.append(
        GuardrailCheck(
            name="input_length_budget",
            stage="input",
            severity="warn" if too_long else "pass",
            passed=not too_long,
            message="Input exceeds the local planning budget." if too_long else "Within budget.",
        )
    )
    for check in checks:
        _record(check, request_id)
    blocking = [check for check in checks if check.severity == "block" and not check.passed]
    if blocking:
        names = ", ".join(check.name for check in blocking)
        raise ValueError(f"Guardrail blocked input: {names}")
    return checks


def check_output(text: str, request_id: str | None = None) -> list[GuardrailCheck]:
    required = ["Path to completion", "Steps", "Risks", "Summary"]
    missing = [section for section in required if section.lower() not in text.lower()]
    checks = [
        GuardrailCheck(
            name="required_plan_sections",
            stage="output",
            severity="warn" if missing else "pass",
            passed=not missing,
            message=f"Missing sections: {', '.join(missing)}" if missing else "All required sections present.",
        ),
        GuardrailCheck(
            name="empty_output",
            stage="output",
            severity="block" if not text.strip() else "pass",
            passed=bool(text.strip()),
            message="Model returned an empty plan." if not text.strip() else "Output present.",
        ),
    ]
    for check in checks:
        _record(check, request_id)
    if not text.strip():
        raise ValueError("Guardrail blocked output: empty_output")
    return checks


def guardrail_summary(limit: int = 100) -> dict:
    rows = read_jsonl(GUARDRAIL_EVENT_LOG_FILE, limit=limit)
    blocked = [row for row in rows if row.get("severity") == "block" and not row.get("passed")]
    warned = [row for row in rows if row.get("severity") == "warn" and not row.get("passed")]
    return {
        "artifact_path": str(GUARDRAIL_EVENT_LOG_FILE),
        "event_count": len(rows),
        "blocked_count": len(blocked),
        "warning_count": len(warned),
        "recent_events": rows[-20:],
    }
