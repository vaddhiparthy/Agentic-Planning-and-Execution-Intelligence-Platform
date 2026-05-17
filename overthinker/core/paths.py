from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ROOT / "overthinker"
UI_DIR = ROOT / "ui"

CONFIG_DIR = ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "overthinker.yaml"

DATA_DIR = ROOT / "data"
PRIVATE_DATA_DIR = DATA_DIR / "private"
DATABASE_FILE = PRIVATE_DATA_DIR / "overthinker.sqlite3"
PROMPT_OVERRIDE_DIR = PRIVATE_DATA_DIR / "prompts"
OPERATIONS_DIR = PRIVATE_DATA_DIR / "operations"
PROMPT_REGISTRY_FILE = OPERATIONS_DIR / "prompt_registry.json"
LLM_CALL_LOG_FILE = OPERATIONS_DIR / "llm_call_log.jsonl"
GUARDRAIL_EVENT_LOG_FILE = OPERATIONS_DIR / "guardrail_events.jsonl"
EVAL_RESULT_LOG_FILE = OPERATIONS_DIR / "eval_results.jsonl"

DEFAULT_PROMPTS_DIR = PACKAGE_DIR / "resources" / "prompts"
EVAL_SUITE_DIR = ROOT / "evals" / "suites"

LEGACY_GOALS_DIR = DATA_DIR / "goals"
LEGACY_FEEDBACK_DIR = DATA_DIR / "feedback"
LEGACY_RUNS_CURRENT_DIR = DATA_DIR / "runs" / "current"
LEGACY_RUNS_PAST_DIR = DATA_DIR / "runs" / "past"
