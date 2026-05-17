# ASTRA-X Overthinker v2

ASTRA-X Overthinker is a FastAPI-based operations planning service. It maintains scoped goals, operator feedback, model-backed planning runs, scheduler controls, and persistent run history behind a clean public demonstration surface.

The public portfolio page is published at:

```text
https://surya.vaddhiparthy.com/overthinker/
```

The root route is designed for portfolio review. It presents planning iteration playback and concise documentation without requiring live model credentials. The operational console remains available separately at `/ui/overthinker.html`.

## Public Surface

| Route | Purpose |
|---|---|
| `/` | Portfolio-style two-tab project page |
| `/demo` | Same public demonstration page |
| `/api/demo/frozen-runs` | Demo run payload used by the public playback |
| `/api/operations/evidence` | Local implementation artifacts for router, prompt registry, guardrails, and evals |
| `/api/evals/run` | Executes the local static evaluation suite |
| `/ui/overthinker.html` | Operational console for goals, runs, feedback, scheduling, and configuration |
| `/api/health` | Service health and runtime readiness |

The portfolio website links this project from the home page, portfolio page, and case-study page. The project title opens the public page, and the paired action icons open the public demonstration and GitHub repository.

The public page has two sections:

- **Live Demonstration**: yearly and monthly task chains that show how a task improves as feedback is added across iterations.
- **Documentation**: implemented architecture, public demo contract, storage/runtime design, and planned expansion boundaries.

The demo is framed around the core Overthinker concept: a goal is not answered once and forgotten; it is revisited, corrected with user feedback, and converted into a sharper execution plan over time.

## Core Capabilities

- Goal management by scope: `daily`, `weekly`, and `yearly`
- Feedback capture for future planning iterations
- Manual and scheduled planning loops
- Model router wrapper for Ollama and OpenAI-compatible endpoints with request metadata capture
- Prompt registry with production prompt versions and render-time variable validation
- Guardrail checks for sensitive input patterns, prompt-injection phrases, length budget, empty output, and required plan sections
- Local static evaluation harness using JSONL suites and persisted pass/fail result artifacts
- Persistent current and archived run history
- Parsed run sections for structured review
- Runtime diagnostics for provider readiness, storage configuration, and scheduler state
- SQLite fallback and PostgreSQL-backed operation

## AI Operations Evidence

This version intentionally avoids S3, Grafana, Terraform, and lakehouse infrastructure. The implemented AI-operations layer is local-first and inspectable:

| Component | Artifact |
|---|---|
| Prompt registry | `data/private/operations/prompt_registry.json` |
| Model router call log | `data/private/operations/llm_call_log.jsonl` |
| Guardrail event log | `data/private/operations/guardrail_events.jsonl` |
| Evaluation results | `data/private/operations/eval_results.jsonl` |
| Evaluation suite | `evals/suites/planning_basic.jsonl` |

The evidence endpoint summarizes these artifacts:

```text
GET /api/operations/evidence
```

The evaluation harness can be run through:

```text
POST /api/evals/run
{"suite": "planning_basic"}
```

## Storage Layout

The production-style default uses PostgreSQL:

| Setting | Default |
|---|---|
| Database | `astrax` |
| Schema | `dev` |
| Table prefix | `overthinker_` |

Primary tables:

- `dev.overthinker_goal_documents`
- `dev.overthinker_goal_items`
- `dev.overthinker_feedback`
- `dev.overthinker_runs`
- `dev.overthinker_run_sections`

SQLite remains available as a local fallback backend.

## Project Structure

```text
.
├─ overthinker/
│  ├─ api/          # FastAPI routes and diagnostics endpoints
│  ├─ core/         # configuration, models, and filesystem paths
│  ├─ resources/    # bundled prompt defaults
│  ├─ services/     # planner, scheduler, and model calls
│  ├─ storage/      # SQLite/PostgreSQL repositories and migration helpers
│  └─ demo_content.py
├─ tests/           # repository, planner, and route smoke tests
├─ ui/              # operational browser console
├─ config/          # runtime config, ignored by git
├─ data/            # runtime state and local data, ignored by git
├─ app.py           # ASGI entrypoint
└─ run_server.py    # local server launcher
```

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_server.py
```

Open:

```text
http://localhost:8432/
```

The operational console is available at:

```text
http://localhost:8432/ui/overthinker.html
```

## Operating Flow

1. Add or revise goals in the console.
2. Add feedback when priorities, constraints, or review comments change.
3. Run a manual iteration or enable scheduled runs.
4. Review the current plan and archived runs.
5. Publish the iteration playback through the public demo page.

## Configuration

Runtime configuration is stored in:

```text
config/overthinker.yaml
```

Prompt overrides can be placed in:

```text
data/private/prompts/
```

Bundled prompt defaults are stored under:

```text
overthinker/resources/prompts/
```

## Testing

```powershell
python -m unittest discover -s tests -v
```

The test suite covers repository initialization, run persistence, planner metadata, public demo routing, demo run exposure, evidence endpoints, evaluation execution, and health diagnostics.
