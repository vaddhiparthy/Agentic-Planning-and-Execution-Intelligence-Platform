from __future__ import annotations

import json
from pathlib import Path

from overthinker.core.paths import EVAL_RESULT_LOG_FILE, EVAL_SUITE_DIR
from overthinker.services.artifacts import append_jsonl, new_artifact_id, read_jsonl, utc_now_iso
from overthinker.services.guardrails import check_output


DEFAULT_SUITE = [
    {
        "case_id": "planning_sections_present",
        "name": "Plan contains required operating sections",
        "input": "Build a public demo page and preserve the operator console.",
        "candidate_output": """## Path to completion
Create a public route and keep the console available.

## Steps
1. Build the demo page.
2. Add demo playback samples.
3. Keep console links separate.

## Risks
Scope creep can make the page misleading.

## Summary
Ship the public demo while keeping operation separate.""",
        "expected_terms": ["Path to completion", "Steps", "Risks", "Summary"],
    },
    {
        "case_id": "feedback_refinement_visible",
        "name": "Plan explains feedback-driven improvement",
        "input": "Improve a yearly task after user feedback.",
        "candidate_output": """## Path to completion
Use feedback as retained planning memory.

## Steps
1. Show the starting task.
2. Show the feedback.
3. Show the improved next plan.

## Risks
The visitor may not understand why versions matter.

## Summary
The output must make refinement visible.""",
        "expected_terms": ["feedback", "improved", "plan"],
    },
]


def ensure_default_suite() -> Path:
    EVAL_SUITE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVAL_SUITE_DIR / "planning_basic.jsonl"
    if not path.exists():
        with path.open("w", encoding="utf-8") as handle:
            for row in DEFAULT_SUITE:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def load_suite(path: Path | None = None) -> list[dict]:
    path = path or ensure_default_suite()
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def run_static_eval_suite(suite_name: str = "planning_basic") -> dict:
    path = ensure_default_suite() if suite_name == "planning_basic" else EVAL_SUITE_DIR / f"{suite_name}.jsonl"
    cases = load_suite(path)
    run_id = new_artifact_id("eval")
    results = []
    for case in cases:
        output = case.get("candidate_output", "")
        guardrail_passed = True
        guardrail_message = "pass"
        try:
            check_output(output, request_id=run_id)
        except ValueError as exc:
            guardrail_passed = False
            guardrail_message = str(exc)
        expected_terms = case.get("expected_terms") or []
        missing = [term for term in expected_terms if term.lower() not in output.lower()]
        passed = guardrail_passed and not missing
        result = {
            "eval_run_id": run_id,
            "case_id": case["case_id"],
            "case_name": case["name"],
            "created_at": utc_now_iso(),
            "suite": suite_name,
            "passed": passed,
            "guardrail_passed": guardrail_passed,
            "guardrail_message": guardrail_message,
            "missing_terms": missing,
        }
        append_jsonl(EVAL_RESULT_LOG_FILE, result)
        results.append(result)
    return {
        "eval_run_id": run_id,
        "suite": suite_name,
        "case_count": len(results),
        "passed_count": sum(1 for row in results if row["passed"]),
        "failed_count": sum(1 for row in results if not row["passed"]),
        "results": results,
        "artifact_path": str(EVAL_RESULT_LOG_FILE),
        "suite_path": str(path),
    }


def eval_summary(limit: int = 100) -> dict:
    rows = read_jsonl(EVAL_RESULT_LOG_FILE, limit=limit)
    return {
        "artifact_path": str(EVAL_RESULT_LOG_FILE),
        "suite_path": str(ensure_default_suite()),
        "result_count": len(rows),
        "passed_count": sum(1 for row in rows if row.get("passed")),
        "failed_count": sum(1 for row in rows if not row.get("passed")),
        "recent_results": rows[-20:],
    }
