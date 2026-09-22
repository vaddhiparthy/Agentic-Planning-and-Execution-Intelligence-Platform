# Agentic Planning and Execution Intelligence Platform

A FastAPI service that turns scoped goals into execution plans and keeps
revising them. Goals are held per scope (`daily`, `weekly`, `yearly`); operator
feedback accumulates against a scope and is replayed into every later planning
run, so a plan is not answered once but corrected over time. Runs are persisted
with the provider and model that produced them.

The service is internally named ASTRA-X Overthinker and the Python package is
`overthinker`.

Live demonstration: https://vaddhiparthy.com/overthinker/

A language-model endpoint is required for real planning runs. The default
provider is a local Ollama server; any OpenAI-compatible chat-completions
endpoint is the alternative. The demonstration page replays stored runs and
needs no credentials.

## How It Works

A planning iteration (`services/planner.py::run_iteration`) runs per scope:

1. **Assemble context** — load the scope's goal document, format the active
   items with their 1-5 priority and details, append context notes, pull the
   last 12 feedback entries, and read the current plan.
2. **Render prompts** — the prompt registry renders `planner_system`,
   `planner_persona`, and `planner_user_payload`. Rendering validates that every
   declared required variable is supplied.
3. **Guard the input** — `check_input` scans for email, SSN, and API-key-shaped
   patterns (blocking), prompt-injection phrasing (blocking), and an 18,000
   character budget (warning). Every check is appended to the guardrail event
   log; a blocking failure raises before any model call.
4. **Route the call** — `route_llm_call` dispatches to Ollama or the
   OpenAI-compatible path, times the request, estimates prompt and completion
   tokens, and appends the outcome to the call log whether it succeeded or
   failed.
5. **Guard the output** — `check_output` warns on missing required sections
   (`Path to completion`, `Steps`, `Risks`, `Summary`) and blocks on empty
   output.
6. **Persist** — the plan is stored as the current run for the scope, parsed
   into sections, and the previous current run is retained in history along with
   the provider, configured model, and effective model.

Before running, the iteration refuses scopes with no active goals and enforces
`rate_limit_per_day` against the count of runs already made today.

**Model routing.** In Ollama mode the router lists installed models before
calling `/api/chat` and refuses the call outright if the configured tag is not
installed, naming a suggested replacement drawn from a preference list
(`qwen2.5`, `qwen3`, `llama3.1`, `llama3`, `glm-4.7`, `llama3.2`); the same
suggestion drives the readiness fields in `/api/health`. The OpenAI-compatible
path posts to `/v1/chat/completions` with `temperature` and `max_tokens` applied
and takes the effective model name from the response. Ollama calls do not carry
those sampling parameters. Both configured and effective model names are
recorded on every run.

**Scheduler.** An asyncio loop tied to the application lifespan. It starts only
when `schedule.autopilot` is enabled, then walks the configured scopes on an
interval derived from `hourly_iterations` (`3600 / n`, floored at 300 seconds),
reloading configuration each pass. It skips quiet hours, skips scopes already at
their daily rate limit, and records the last error without stopping.

**Evaluation harness.** `run_static_eval_suite` loads a JSONL suite, passes each
case's stored candidate output through the output guardrails, checks for
expected terms, and appends per-case results to the eval result log. The
`planning_basic` suite is written to disk from a built-in default if absent. The
cases carry fixed candidate outputs, so the harness exercises the guardrail and
scoring path rather than the model.

## API

| Route | Purpose |
| --- | --- |
| `GET /`, `GET /demo` | Demonstration page: stored planning iterations plus implementation notes |
| `GET /api/demo/frozen-runs` | Stored run payload behind the demonstration playback |
| `GET /api/operations/evidence` | Summaries of the router, prompt registry, guardrail, and eval artifacts |
| `POST /api/evals/run` | Execute a static evaluation suite |
| `GET /api/health` | Provider readiness, scheduler snapshot, and per-scope readiness |
| `GET/PUT /api/goals/{scope}` | Read and replace a scope's goal document |
| `POST /api/goals/{scope}/import-markdown` | Import goals from markdown |
| `GET /api/feedback/{scope}`, `POST /api/feedback` | Read and append feedback |
| `POST /api/runs` | Run an iteration now |
| `GET /api/runs/{scope}/current`, `GET /api/runs/{scope}/history` | Current plan and run history |
| `POST /api/runs/{scope}/archive` | Archive the current run |
| `GET/POST /api/config`, `GET /api/control-panel` | Runtime configuration |
| `GET /api/providers/ollama/models` | Installed Ollama models |
| `/ui/overthinker.html` | Operator console for goals, runs, feedback, scheduling, and configuration |

## Local Artifacts

The operations layer is local-first and file-inspectable. Nothing is shipped to
an external observability backend.

| Component | Artifact |
| --- | --- |
| Prompt registry | `data/private/operations/prompt_registry.json` |
| Model router call log | `data/private/operations/llm_call_log.jsonl` |
| Guardrail event log | `data/private/operations/guardrail_events.jsonl` |
| Evaluation results | `data/private/operations/eval_results.jsonl` |
| Evaluation suite | `evals/suites/planning_basic.jsonl` |

`data/` and `config/` are runtime directories and are excluded from version
control.

## Configuration

Configuration lives in `config/overthinker.yaml`, which is created with defaults
on first load.

| Setting | Default | Purpose |
| --- | --- | --- |
| `model.provider` | `ollama` | `ollama`, otherwise the OpenAI-compatible path |
| `model.model_name` | `qwen2.5:7b-instruct` | Configured model tag |
| `model.api_base` | `http://127.0.0.1:11434` | Provider endpoint |
| `model.api_key_env` | `OPENAI_API_KEY` | Environment variable holding the API key |
| `model.temperature` | `0.4` | Sampling temperature (0-2) |
| `model.max_tokens` | `1500` | Completion budget (128-32000) |
| `model.request_timeout_seconds` | `180` | Per-call timeout (5-600) |
| `schedule.autopilot` | `false` | Whether the scheduler loop runs |
| `schedule.hourly_iterations` | `1` | Runs per hour (1-12) |
| `schedule.rate_limit_per_day` | `8` | Per-scope daily run cap (1-500) |
| `schedule.quiet_hours` | `02:00-04:00` | Window in which cycles are skipped |
| `schedule.scopes` | all three | Scopes the scheduler iterates |
| `runtime.host` / `runtime.port` | `0.0.0.0` / `8432` | Bind address |
| `runtime.cors_origins` | `*` | Allowed origins |
| `storage.backend` | `sqlite` | `sqlite` or `postgres` |

**Prompts.** Defaults are defined in code (`DEFAULT_PROMPTS` in
`services/prompt_registry.py`), so the service runs with no prompt files
present. The `planner_system` and `planner_persona` templates can be overridden
at registry seed time by files named `system_planner.txt` and
`persona_general.txt`, read from `data/private/prompts/` first and
`overthinker/resources/prompts/` second. Neither directory is committed.

**Storage.** SQLite is the default and writes to
`data/private/overthinker.sqlite3`. Setting `storage.backend` to `postgres`
switches to the PostgreSQL repository, which defaults to database `astrax`,
schema `dev`, and table prefix `overthinker_`, giving
`dev.overthinker_goal_documents`, `dev.overthinker_goal_items`,
`dev.overthinker_feedback`, `dev.overthinker_runs`, and
`dev.overthinker_run_sections`.

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_server.py
```

With default settings the service listens on port 8432, so on the machine
running it the UI is at `http://localhost:8432/` and the operator console at
`http://localhost:8432/ui/overthinker.html`.

Typical loop: add or revise goals in the console, add feedback when priorities
or constraints change, run an iteration manually or enable the scheduler, then
review the current plan and archived runs.

## Testing

```powershell
python -m unittest discover -s tests -v
```

Eight tests covering repository initialization, run persistence with model
metadata, planner metadata propagation with the model call patched, the
demonstration route and its run payload, the evidence endpoint, static
evaluation execution, and health scope readiness. There is no CI workflow in
this repository.

## Repository Layout

```text
.
├─ overthinker/
│  ├─ api/routes.py        # FastAPI routes and runtime diagnostics
│  ├─ core/                # config, pydantic models, filesystem paths
│  ├─ services/            # planner, scheduler, model router, prompts, guardrails, evals
│  ├─ storage/             # SQLite and PostgreSQL repositories, migration helpers
│  └─ demo_content.py      # stored runs and the rendered demonstration page
├─ evals/suites/           # JSONL evaluation suites
├─ tests/
├─ ui/                     # operator console
├─ app.py                  # ASGI entrypoint
└─ run_server.py           # local launcher
```

## Scope And Limitations

- Local-first by design: no object storage, metrics backend, or infrastructure
  provisioning. The operations artifacts are append-only JSONL and JSON files on
  disk, with no rotation or retention policy.
- The evaluation suite scores fixed candidate outputs against expected terms; it
  does not call a model and is not a model-quality benchmark.
- Guardrails are regular-expression and structural checks, not a classifier.
- The scheduler is an in-process asyncio loop tied to the application lifespan;
  it does not survive a restart mid-cycle and does not coordinate across
  replicas.
- CORS defaults to all origins, which suits local use but not a public
  deployment.
- Only two provider paths are implemented, with no retry or cross-provider
  fallback.
