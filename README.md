# ASTRA-X Overthinker — Persona-Aware Goal Engine

Flask + APScheduler backend that runs an LLM over a Markdown goal vault, refines step plans, and appends structured changelogs and progress notes.  
Goals live in Markdown files (`daily`, `monthly`, `yearly` + per-item files); a persona file grounds the model so it produces realistic, non-hallucinated next actions.

---

## What it does

- Reads **master goal lists** from Markdown:
  - Daily, monthly, yearly files (e.g. `- [ ] D-001 Write X`).
  - Each line is parsed into `{id, title, scope, done}`.
- Maintains **one Markdown file per goal** in an `items` directory:
  - Front-matter style metadata (scope, iteration count, last_runtime, summary).
  - Sections:
    - `## Original Goal`
    - `## Path to completion`
    - `## Change Log`
    - `## Progress (your notes)`
- Runs an **iteration loop** (manual or scheduled) that:
  - Loads `persona.md` and the current goal file.
  - Sends goal + steps + recent progress to an LLM (OpenAI or Ollama).
  - Parses a constrained `STEPS: ... / SUMMARY: ...` response.
  - Updates `## Path to completion`, increments `iteration_count`, stamps `last_runtime`.
  - Adds a **short changelog note** (≤ 60 chars) per run.
  - Writes a **daily digest** into `runs/DATE-digest.md`.
- Provides a **web UI**:
  - `/` — index with daily / monthly / yearly open goals.
  - `/goal/<gid>` — detail page for a single goal.
  - `/goal/<gid>/append` — append timestamped progress text and optionally mark done.
- Provides **quick add** and **control APIs**:
  - `/quickadd/<scope>` — POST newline-separated goals; auto-IDs missing IDs and seeds per-goal files.
  - `/api/run_once` — run one iteration over all open goals.
  - `/api/scheduler/status` — show if the APScheduler job is enabled + next run time.
- When a master checklist item is marked `[x]`:
  - The corresponding goal file is **archived into `done/`** with a timestamped filename.
  - Iterations skip it going forward.

Everything is timezone-aware (America/Detroit), with consistent timestamp formatting for both UI and stored notes.

---

## Architecture / Flow

### Files & directories

The app is configured via `config.yaml` and runs against a “vault root”:

- `config.yaml`
  - `vault_root`: base path of your Overthinker vault.
  - `daily_file`, `monthly_file`, `yearly_file`: paths (relative to `vault_root`) to the master Markdown lists.
  - `items_dir`, `runs_dir`, `done_dir`: subdirectory names for items, run digests, and archived goals.
  - `llm_mode`: `"none" | "ollama" | "openai"`.
  - `ollama`: `{ base_url, model }`.
  - `openai`: `{ model, api_key_env }`.
  - `iteration_interval_minutes`: APScheduler interval.

- Under `vault_root`:
  - `daily.md` / `monthly.md` / `yearly.md` (names depend on config):
    ```markdown
    # Daily
    - [ ] D-001 Example daily goal
    - [x] D-002 Completed goal
    ```
  - `items/` — one `ID.md` file per goal (`D-001.md`, `M-003.md`, etc.).
  - `runs/` — digests like `2025-11-13-digest.md`.
  - `done/` — archived items: `20251113-153045_D-001.md`.
  - `persona.md` — long-form persona / constraints for the LLM.

- App files:
  - `app.py` — this service.
  - `templates/index.html` — dashboard view (lists open goals by scope).
  - `templates/goal.html` — per-goal detail view.

