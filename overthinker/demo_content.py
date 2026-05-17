from __future__ import annotations

import html
import json


DEMO_TASKS = [
    {
        "task_id": "yearly-portfolio-system",
        "scope": "yearly",
        "title": "Build a portfolio-grade AI and data engineering project system",
        "description": (
            "A long-range planning task showing how ASTRA-X starts with an ambitious objective, "
            "then refines the execution strategy as feedback is added across iterations."
        ),
        "iterations": [
            {
                "label": "Iteration 0",
                "state": "Seed task",
                "feedback": "No user feedback yet.",
                "output": """## Task
Build a portfolio-grade AI and data engineering project system.

## Initial Steps
1. Identify projects that demonstrate credible engineering depth.
2. Create public pages for each project.
3. Document the architecture and deployment approach.
4. Keep the execution plan reviewed every week.

## Assessment
This is a broad objective. It needs prioritization, delivery gates, and a stronger definition of what makes a project portfolio-grade.""",
            },
            {
                "label": "Iteration 1",
                "state": "First plan generated",
                "feedback": "Prioritize finished artifacts over planning documents. Each project must have a live demo, technical proof, and a clean README.",
                "output": """## Refined Plan
1. Select two projects that can be shipped end-to-end instead of spreading effort across many ideas.
2. For each project, publish a public demo route, repository README, and architecture page.
3. Keep any advanced features marked as planned unless they are already implemented.
4. Build a review checklist before moving to the next project.

## Improvement From Feedback
The plan now favors finished artifacts and reviewer-visible proof instead of abstract planning.""",
            },
            {
                "label": "Iteration 2",
                "state": "Feedback incorporated",
                "feedback": "Make the public demo explain what changed between iterations, not just show a final answer.",
                "output": """## Stronger Execution Model
1. Convert each project demo into a before-and-after evidence surface.
2. Show the starting task, the generated plan, the user feedback, and the next improved plan.
3. Publish the iteration playback so visitors can inspect the workflow without live credentials.
4. Keep the operational console separate from the public demo.

## Final Direction
The portfolio now demonstrates process quality, not only output quality. ASTRA-X becomes the system that repeatedly revisits a goal until the plan is sharper, more grounded, and easier to execute.""",
            },
        ],
    },
    {
        "task_id": "monthly-demo-release",
        "scope": "monthly",
        "title": "Release ASTRA-X as a clean public demonstration",
        "description": (
            "A shorter execution task showing how monthly work is decomposed into concrete release steps, "
            "then tightened after usability feedback."
        ),
        "iterations": [
            {
                "label": "Iteration 0",
                "state": "Seed task",
                "feedback": "No user feedback yet.",
                "output": """## Task
Release ASTRA-X as a clean public demonstration.

## Initial Steps
1. Start the FastAPI service.
2. Add a public landing page.
3. Keep the old console available.
4. Add documentation.

## Assessment
The plan is technically correct but too generic. It does not explain the core philosophy of ASTRA-X.""",
            },
            {
                "label": "Iteration 1",
                "state": "First plan generated",
                "feedback": "The demo should show the overthinking loop: task, generated plan, user feedback, then a better plan.",
                "output": """## Revised Release Plan
1. Replace static run cards with an iteration playback interface.
2. Add task selectors for yearly and monthly scopes.
3. Add previous and next controls to move through plan revisions.
4. Show feedback as a first-class part of the run history.

## Improvement From Feedback
The demo now explains why the project is called Overthinker: it repeatedly revisits the same goal with more context.""",
            },
            {
                "label": "Iteration 2",
                "state": "Ready for public review",
                "feedback": "Explain this to visitors in plain language: outsource the repeated mental loop to a system that remembers feedback.",
                "output": """## Release Narrative
ASTRA-X Overthinker is a planning system for people who revisit the same objective repeatedly until the plan becomes practical. Instead of keeping that loop in your head, the system stores the goal, remembers feedback, and generates the next sharper version.

## Public Demo Requirements
1. Show yearly and monthly tasks.
2. Let visitors step through the iteration chain.
3. Display the feedback that caused each improvement.
4. Keep live execution in the operator console and public review in the demo surface.

## Release Decision
This release separates the public demonstration from the operational console so visitors can understand the refinement loop without needing access to runtime controls.""",
            },
        ],
    },
]


DEMO_RUNS = [
    {
        "run_id": f"{task['task_id']}-{index}",
        "task_id": task["task_id"],
        "scope": task["scope"],
        "title": task["title"],
        "iteration": item["label"],
        "state": item["state"],
        "feedback": item["feedback"],
        "plan_markdown": item["output"],
        "trigger": "demo playback",
    }
    for task in DEMO_TASKS
    for index, item in enumerate(task["iterations"])
]


DOCUMENTATION_SECTIONS = [
    {
        "title": "Product Philosophy",
        "body": (
            "ASTRA-X is called Overthinker because it externalizes the repeated planning loop. "
            "A person starts with a goal, reviews the generated plan, adds feedback, and lets the system "
            "produce the next sharper version. The value is not one answer; the value is memory-backed refinement."
        ),
        "points": [
            "Iteration 0 captures the seed task and initial assumptions.",
            "Later iterations preserve feedback as part of the decision trail.",
            "Each generated plan becomes a comparable version, not a disposable chat reply.",
            "The public playback makes the loop understandable without requiring live model credentials.",
        ],
    },
    {
        "title": "Implemented Components",
        "body": (
            "The current implementation adds a local-first AI operations layer around the existing planning system. "
            "The purpose is to prove the operating mechanics behind the demo, not only display a polished page."
        ),
        "points": [
            "Model router: all planner model calls flow through a routing wrapper that records provider, configured model, effective model, request status, latency, estimated prompt tokens, and estimated completion tokens.",
            "Prompt registry: production prompt templates are stored in a local registry with name, version, status, purpose, template text, and required-variable contract.",
            "Guardrails: input checks block sensitive-pattern and prompt-injection style payloads; output checks validate that generated plans are present and contain required operating sections.",
            "Evaluation harness: a JSONL suite executes deterministic planning checks and persists pass/fail evidence.",
            "Evidence endpoint: `/api/operations/evidence` summarizes the router, registry, guardrail, and evaluation artifacts in one machine-readable contract.",
            "Operator console: `/ui/overthinker.html` remains the working surface for goals, feedback, runs, scheduler settings, and runtime configuration.",
        ],
    },
    {
        "title": "Implementation Artifacts",
        "body": (
            "The implementation produces local artifacts that can be inspected directly. These files are the evidence layer "
            "for the website and API. They are intentionally lightweight so the project can run locally without S3, Grafana, or Terraform."
        ),
        "points": [
            "Prompt registry artifact: `data/private/operations/prompt_registry.json`.",
            "Model router call log: `data/private/operations/llm_call_log.jsonl`.",
            "Guardrail event log: `data/private/operations/guardrail_events.jsonl`.",
            "Evaluation results log: `data/private/operations/eval_results.jsonl`.",
            "Evaluation suite definition: `evals/suites/planning_basic.jsonl`.",
            "Public summary endpoint: `GET /api/operations/evidence`.",
        ],
    },
    {
        "title": "How Evidence Is Produced",
        "body": (
            "The project can produce fresh evidence from local execution. A live planner run produces router and guardrail artifacts. "
            "A local evaluation run produces evaluation artifacts. The prompt registry initializes when the application reads the registry."
        ),
        "points": [
            "Run the app with `python run_server.py` and open `http://127.0.0.1:8432/`.",
            "Inspect all implementation evidence with `GET http://127.0.0.1:8432/api/operations/evidence`.",
            "Run the evaluation harness with `POST http://127.0.0.1:8432/api/evals/run` and body `{\"suite\":\"planning_basic\"}`.",
            "Generate live router evidence by running a planner iteration from the operator console after a provider is configured.",
            "Generate guardrail evidence by running a normal planner flow or by executing the evaluation harness, which validates candidate outputs.",
            "Inspect raw artifacts under `data/private/operations/` when a file-level audit is needed.",
        ],
    },
    {
        "title": "What Can Run Live",
        "body": (
            "The website demonstration is safe for public review, while the operator console can execute the working planning loop. "
            "Live execution depends on configured model access, but the evidence and evaluation endpoints are available locally."
        ),
        "points": [
            "Live immediately: public demo, demo run payload, health endpoint, evidence summary endpoint, and local evaluation suite.",
            "Live when provider is configured: planner iteration execution through the operator console or `POST /api/runs`.",
            "Captured during live planner execution: model provider, selected model, request status, latency, estimated tokens, guardrail outcomes, run metadata, and generated plan sections.",
            "Captured during eval execution: suite name, case IDs, pass/fail status, missing expected terms, guardrail result, and result artifact path.",
            "Not required for this phase: object storage, external dashboards, infrastructure provisioning, or cloud warehouse services.",
        ],
    },
    {
        "title": "Current Boundaries",
        "body": (
            "The implementation focuses on the practical AI-operations core. The heavier parts of the expansion markdown remain intentionally out of scope for this version."
        ),
        "points": [
            "Implemented: planning service, scoped goals, feedback capture, run history, scheduler lifecycle, public demo.",
            "Implemented: prompt registry, model router capture, guardrail event logging, and static evaluation suite.",
            "Not included: S3/Iceberg/dbt, Grafana/Phoenix, Terraform, and multi-surface deployment automation.",
            "The project is presented as a local-first AI operations planning system with inspectable evidence, not as a full cloud LLMOps platform.",
        ],
    },
    {
        "title": "Reviewer Explanation",
        "body": (
            "A visitor should understand that ASTRA-X is not a chatbot clone. It is an execution-planning loop that "
            "keeps task context, feedback, and plan versions together."
        ),
        "points": [
            "Choose a scope such as yearly or monthly.",
            "Inspect the seed task and first generated plan.",
            "Move forward to see the feedback applied.",
            "Compare the later plan to the earlier plan and observe how the output becomes more specific.",
        ],
    },
]


def _markdown_to_html(markdown_text: str) -> str:
    blocks: list[str] = []
    list_items: list[str] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            if list_items:
                blocks.append("<ol>" + "".join(list_items) + "</ol>")
                list_items = []
            continue
        if line.startswith("## "):
            if list_items:
                blocks.append("<ol>" + "".join(list_items) + "</ol>")
                list_items = []
            blocks.append(f"<h4>{html.escape(line[3:])}</h4>")
        elif len(line) > 2 and line[0].isdigit() and line[1:3] in (". ", ") "):
            list_items.append(f"<li>{html.escape(line[3:])}</li>")
        elif line.startswith("- "):
            list_items.append(f"<li>{html.escape(line[2:])}</li>")
        else:
            if list_items:
                blocks.append("<ol>" + "".join(list_items) + "</ol>")
                list_items = []
            blocks.append(f"<p>{html.escape(line)}</p>")
    if list_items:
        blocks.append("<ol>" + "".join(list_items) + "</ol>")
    return "\n".join(blocks)


def render_demo_page() -> str:
    tasks_json = json.dumps(DEMO_TASKS)
    runs_json = json.dumps(DEMO_RUNS)
    first_task = DEMO_TASKS[0]
    first_iteration = first_task["iterations"][0]
    first_plan_html = _markdown_to_html(first_iteration["output"])
    docs_html = "\n".join(
        f"""
        <article class="doc-card">
          <h3>{html.escape(section["title"])}</h3>
          <p>{html.escape(section["body"])}</p>
          <ul>{''.join(f'<li>{html.escape(point)}</li>' for point in section["points"])}</ul>
        </article>
        """
        for section in DOCUMENTATION_SECTIONS
    )
    task_buttons = "\n".join(
        f"""
        <button class="task-selector {'active' if index == 0 else ''}" data-task-index="{index}">
          <span>{html.escape(task["title"])}</span>
          <small>{html.escape(task["scope"].title())} task / iteration playback</small>
        </button>
        """
        for index, task in enumerate(DEMO_TASKS)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ASTRA-X Overthinker Demo</title>
  <style>
    :root {{
      --ink: #16211f;
      --muted: #61706c;
      --paper: #f5f0e7;
      --line: rgba(42, 62, 57, 0.16);
      --accent: #1b7f79;
      --accent-2: #b96d45;
      --deep: #102b29;
      --shadow: 0 24px 80px rgba(24, 38, 35, 0.16);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(circle at 15% 5%, rgba(27, 127, 121, 0.18), transparent 32rem),
        radial-gradient(circle at 88% 18%, rgba(185, 109, 69, 0.16), transparent 30rem),
        linear-gradient(145deg, #f7f1e6 0%, #eee6d8 52%, #e8decc 100%);
      font-family: Georgia, "Times New Roman", serif;
    }}
    a {{ color: inherit; }}
    .shell {{ width: min(1180px, calc(100vw - 36px)); margin: 0 auto; padding: 30px 0 54px; }}
    .topbar {{ display: flex; justify-content: space-between; align-items: center; gap: 18px; margin-bottom: 26px; }}
    .brand-mark, .nav-links a, .hero-card, .stat-card, .tab-panel, .doc-card, .iteration-card {{
      border: 1px solid var(--line);
      background: rgba(255, 250, 240, 0.88);
      box-shadow: var(--shadow);
    }}
    .brand-mark {{ padding: 13px 18px; border-radius: 22px; backdrop-filter: blur(14px); }}
    .brand-mark strong {{ display: block; letter-spacing: 0.12em; text-transform: uppercase; font-size: 0.72rem; color: var(--accent); }}
    .brand-mark span {{ display: block; margin-top: 4px; font-size: 1rem; font-weight: 700; }}
    .nav-links {{ display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }}
    .nav-links a {{ text-decoration: none; padding: 10px 14px; border-radius: 999px; color: var(--deep); font-size: 0.92rem; box-shadow: none; }}
    .hero {{ display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(300px, 0.75fr); gap: 22px; align-items: stretch; margin-bottom: 22px; }}
    .hero-card {{ padding: 34px; border-radius: 30px; position: relative; overflow: hidden; }}
    .hero-card::after {{ content: ""; position: absolute; width: 210px; height: 210px; right: -60px; bottom: -80px; border-radius: 999px; border: 42px solid rgba(27, 127, 121, 0.08); }}
    .kicker {{ margin: 0 0 12px; text-transform: uppercase; letter-spacing: 0.18em; font-size: 0.76rem; color: var(--accent); font-weight: 700; }}
    h1 {{ margin: 0; max-width: 820px; font-size: clamp(2.7rem, 7vw, 6.4rem); line-height: 0.9; letter-spacing: -0.08em; }}
    .hero-copy {{ margin: 22px 0 0; max-width: 760px; color: var(--muted); font-size: 1.08rem; line-height: 1.65; }}
    .stat-grid {{ display: grid; gap: 14px; }}
    .stat-card {{ padding: 20px; border-radius: 30px; }}
    .stat-card small, .iteration-meta small {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.12em; font-size: 0.68rem; font-weight: 700; }}
    .stat-card strong {{ display: block; margin-top: 8px; font-size: 1.45rem; }}
    .stack-strip {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin: 18px 0 10px; }}
    .stack-chip {{ border: 1px solid var(--line); border-radius: 20px; background: rgba(255, 250, 240, 0.74); padding: 13px 14px; min-height: 74px; }}
    .stack-chip small {{ display: block; color: var(--muted); text-transform: uppercase; letter-spacing: 0.11em; font-size: 0.66rem; font-weight: 700; }}
    .stack-chip strong {{ display: block; margin-top: 7px; font-size: 1rem; }}
    .tabs {{ display: flex; gap: 10px; margin: 24px 0 14px; padding: 7px; border: 1px solid var(--line); border-radius: 999px; background: rgba(255, 250, 240, 0.70); width: fit-content; }}
    .tab-button {{ border: 0; cursor: pointer; padding: 12px 18px; border-radius: 999px; background: transparent; color: var(--deep); font: 700 0.94rem Georgia, "Times New Roman", serif; }}
    .tab-button.active {{ background: var(--deep); color: #fff7e8; box-shadow: 0 12px 24px rgba(16, 43, 41, 0.20); }}
    .tab-panel {{ display: none; padding: 26px; border-radius: 30px; }}
    .tab-panel.active {{ display: block; }}
    .demo-layout {{ display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 18px; }}
    .task-list {{ display: grid; gap: 10px; align-content: start; }}
    .task-selector {{ text-align: left; border: 1px solid var(--line); border-radius: 20px; background: rgba(255, 255, 255, 0.52); padding: 15px; color: var(--ink); cursor: pointer; font-family: inherit; }}
    .task-selector span {{ display: block; font-weight: 700; font-size: 1rem; line-height: 1.3; }}
    .task-selector small {{ display: block; margin-top: 7px; color: var(--muted); }}
    .task-selector.active {{ border-color: rgba(27, 127, 121, 0.55); background: rgba(27, 127, 121, 0.10); box-shadow: inset 4px 0 0 var(--accent); }}
    .iteration-card {{ padding: 24px; border-radius: 30px; box-shadow: none; background: rgba(255, 255, 255, 0.48); }}
    .iteration-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; margin-bottom: 14px; }}
    .iteration-head h2 {{ margin: 0; letter-spacing: -0.03em; }}
    .counter {{ padding: 9px 12px; border-radius: 999px; background: rgba(27, 127, 121, 0.12); color: var(--accent); font-weight: 700; white-space: nowrap; }}
    .iteration-meta {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 18px 0; }}
    .iteration-meta div {{ padding: 12px; border-radius: 16px; background: rgba(16, 43, 41, 0.06); }}
    .iteration-meta strong {{ display: block; margin-top: 4px; font-size: 0.9rem; }}
    .feedback-box {{ border-left: 4px solid var(--accent-2); padding: 13px 15px; background: rgba(185, 109, 69, 0.10); border-radius: 14px; color: #6d4231; margin: 14px 0 18px; }}
    .plan-output {{ padding: 20px; border-radius: 22px; background: #122b29; color: #fff7e8; line-height: 1.58; min-height: 360px; }}
    .plan-output h4 {{ margin: 18px 0 8px; color: #f3c08f; font-size: 1rem; }}
    .plan-output h4:first-child {{ margin-top: 0; }}
    .plan-output p {{ color: rgba(255, 247, 232, 0.82); }}
    .plan-output li {{ margin: 7px 0; }}
    .playback-controls {{ display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 16px; }}
    .playback-controls button {{ border: 1px solid var(--line); border-radius: 999px; padding: 10px 16px; background: rgba(255, 250, 240, 0.82); color: var(--deep); cursor: pointer; font: 700 0.9rem Georgia, "Times New Roman", serif; }}
    .playback-controls button:disabled {{ opacity: 0.38; cursor: not-allowed; }}
    .progress-line {{ flex: 1; height: 8px; border-radius: 999px; background: rgba(16, 43, 41, 0.10); overflow: hidden; }}
    .progress-fill {{ height: 100%; width: 0; background: linear-gradient(90deg, var(--accent), var(--accent-2)); transition: width 180ms ease; }}
    .docs-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .doc-card {{ padding: 22px; border-radius: 30px; box-shadow: none; background: rgba(255, 255, 255, 0.48); }}
    .doc-card h3 {{ margin: 0 0 10px; letter-spacing: -0.03em; }}
    .doc-card p {{ color: var(--muted); line-height: 1.58; }}
    .doc-card li {{ margin: 8px 0; line-height: 1.48; }}
    @media (max-width: 860px) {{
      .hero, .demo-layout, .docs-grid {{ grid-template-columns: 1fr; }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .iteration-meta, .stack-strip {{ grid-template-columns: 1fr; }}
      .tabs {{ width: 100%; }}
      .tab-button {{ flex: 1; }}
      .iteration-head, .playback-controls {{ flex-direction: column; align-items: stretch; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand-mark">
        <strong>ASTRA-X</strong>
        <span>Overthinking outsourced into an execution loop</span>
      </div>
      <nav class="nav-links" aria-label="Project links">
        <a href="/ui/overthinker.html">Operator Console</a>
        <a href="/api/health">Health Endpoint</a>
        <a href="/api/operations/evidence">Implementation Artifacts</a>
        <a href="/api/demo/frozen-runs">Demo Runs API</a>
      </nav>
    </header>

    <section class="hero">
      <div class="hero-card">
        <p class="kicker">Portfolio System / Iterative Planning Demo</p>
        <h1>ASTRA-X Overthinker</h1>
        <p class="hero-copy">
          In the age of AI, the repeated mental loop of planning, second-guessing, refining, and
          incorporating feedback can be externalized. ASTRA-X keeps the goal, the feedback, and every
          revised plan together so a task becomes sharper across iterations instead of disappearing into a chat thread.
        </p>
      </div>
      <aside class="stat-grid" aria-label="Demo facts">
        <div class="stat-card"><small>Demo pattern</small><strong>Task → feedback → better plan</strong></div>
        <div class="stat-card"><small>Review mode</small><strong>Iteration playback</strong></div>
        <div class="stat-card"><small>Working surface</small><strong>/ui/overthinker.html</strong></div>
      </aside>
    </section>

    <section class="stack-strip" aria-label="Implementation stack">
      <div class="stack-chip"><small>API</small><strong>FastAPI service</strong></div>
      <div class="stack-chip"><small>Router</small><strong>Model call capture</strong></div>
      <div class="stack-chip"><small>Feedback</small><strong>Persistent refinement memory</strong></div>
      <div class="stack-chip"><small>Prompts</small><strong>Versioned registry</strong></div>
      <div class="stack-chip"><small>Quality</small><strong>Guardrails + evals</strong></div>
    </section>

    <div class="tabs" role="tablist">
      <button class="tab-button active" data-tab="demo" type="button">Live Demonstration</button>
      <button class="tab-button" data-tab="docs" type="button">Documentation</button>
    </div>

    <section class="tab-panel active" id="demo-panel">
      <div class="demo-layout">
        <aside class="task-list" aria-label="Frozen task chains">{task_buttons}</aside>
        <article class="iteration-card">
          <div class="iteration-head">
            <div>
              <p class="kicker" id="task-scope">{html.escape(first_task["scope"])} task</p>
              <h2 id="task-title">{html.escape(first_task["title"])}</h2>
            </div>
            <div class="counter" id="iteration-counter">Iteration 0 of {len(first_task["iterations"]) - 1}</div>
          </div>
          <p id="task-description">{html.escape(first_task["description"])}</p>
          <div class="iteration-meta">
            <div><small>Current state</small><strong id="iteration-state">{html.escape(first_iteration["state"])}</strong></div>
            <div><small>Feedback memory</small><strong id="feedback-status">None yet</strong></div>
            <div><small>Playback</small><strong id="playback-label">Demo iteration chain</strong></div>
          </div>
          <div class="feedback-box">
            <strong>User feedback at this point:</strong>
            <div id="iteration-feedback">{html.escape(first_iteration["feedback"])}</div>
          </div>
          <div class="plan-output" id="plan-output">{first_plan_html}</div>
          <div class="playback-controls">
            <button id="prev-iteration" type="button">Previous iteration</button>
            <div class="progress-line"><div class="progress-fill" id="progress-fill"></div></div>
            <button id="next-iteration" type="button">Next iteration</button>
          </div>
        </article>
      </div>
    </section>

    <section class="tab-panel" id="docs-panel">
      <div class="docs-grid">{docs_html}</div>
    </section>
  </main>
  <script>
    const demoTasks = {tasks_json};
    const demoRuns = {runs_json};
    let activeTaskIndex = 0;
    let activeIterationIndex = 0;

    const renderMarkdown = (text) => {{
      const lines = text.split("\\n");
      let out = "";
      let inList = false;
      for (const raw of lines) {{
        const line = raw.trim();
        if (!line) {{
          if (inList) {{ out += "</ol>"; inList = false; }}
          continue;
        }}
        if (line.startsWith("## ")) {{
          if (inList) {{ out += "</ol>"; inList = false; }}
          out += `<h4>${{line.slice(3)}}</h4>`;
        }} else if (/^\\d+[.)]\\s/.test(line)) {{
          if (!inList) {{ out += "<ol>"; inList = true; }}
          out += `<li>${{line.replace(/^\\d+[.)]\\s/, "")}}</li>`;
        }} else if (line.startsWith("- ")) {{
          if (!inList) {{ out += "<ol>"; inList = true; }}
          out += `<li>${{line.slice(2)}}</li>`;
        }} else {{
          if (inList) {{ out += "</ol>"; inList = false; }}
          out += `<p>${{line}}</p>`;
        }}
      }}
      if (inList) out += "</ol>";
      return out;
    }};

    const renderIteration = () => {{
      const task = demoTasks[activeTaskIndex];
      const iteration = task.iterations[activeIterationIndex];
      const last = task.iterations.length - 1;
      document.getElementById("task-scope").textContent = `${{task.scope}} task`;
      document.getElementById("task-title").textContent = task.title;
      document.getElementById("task-description").textContent = task.description;
      document.getElementById("iteration-counter").textContent = `${{iteration.label}} of ${{last}}`;
      document.getElementById("iteration-state").textContent = iteration.state;
      document.getElementById("feedback-status").textContent = activeIterationIndex === 0 ? "None yet" : "Applied";
      document.getElementById("iteration-feedback").textContent = iteration.feedback;
      document.getElementById("plan-output").innerHTML = renderMarkdown(iteration.output);
      document.getElementById("prev-iteration").disabled = activeIterationIndex === 0;
      document.getElementById("next-iteration").disabled = activeIterationIndex === last;
      document.getElementById("progress-fill").style.width = `${{(activeIterationIndex / Math.max(last, 1)) * 100}}%`;
    }};

    document.querySelectorAll(".tab-button").forEach((button) => {{
      button.addEventListener("click", () => {{
        document.querySelectorAll(".tab-button").forEach((node) => node.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((node) => node.classList.remove("active"));
        button.classList.add("active");
        document.getElementById(`${{button.dataset.tab}}-panel`).classList.add("active");
      }});
    }});

    document.querySelectorAll(".task-selector").forEach((button) => {{
      button.addEventListener("click", () => {{
        activeTaskIndex = Number(button.dataset.taskIndex);
        activeIterationIndex = 0;
        document.querySelectorAll(".task-selector").forEach((node) => node.classList.remove("active"));
        button.classList.add("active");
        renderIteration();
      }});
    }});

    document.getElementById("prev-iteration").addEventListener("click", () => {{
      activeIterationIndex = Math.max(0, activeIterationIndex - 1);
      renderIteration();
    }});
    document.getElementById("next-iteration").addEventListener("click", () => {{
      const last = demoTasks[activeTaskIndex].iterations.length - 1;
      activeIterationIndex = Math.min(last, activeIterationIndex + 1);
      renderIteration();
    }});
    renderIteration();
  </script>
</body>
</html>"""
