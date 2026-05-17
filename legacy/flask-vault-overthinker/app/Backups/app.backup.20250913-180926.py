# ============================================
# OVERTHINKER BLOCK 1: Imports & Globals
# ============================================
import os, re, json, shutil, datetime as dt
from flask import Flask, render_template, request, redirect
from apscheduler.schedulers.background import BackgroundScheduler
import yaml, requests
from zoneinfo import ZoneInfo

# ============================================
# OVERTHINKER BLOCK 2: Config & Paths
# ============================================
with open("config.yaml","r",encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

ROOT     = CFG["vault_root"].replace("\\","/")
DAILY    = os.path.join(ROOT, CFG["daily_file"])
MONTHLY  = os.path.join(ROOT, CFG["monthly_file"])
YEARLY   = os.path.join(ROOT, CFG["yearly_file"])
ITEMS    = os.path.join(ROOT, CFG["items_dir"])
RUNS     = os.path.join(ROOT, CFG["runs_dir"])
DONE     = os.path.join(ROOT, CFG["done_dir"])
PERSONA  = os.path.join(ROOT, "persona.md")
SETTINGS = os.path.join(ROOT, "_settings.json")
STATE    = os.path.join(ROOT, "_state.json")
for p in (ITEMS, RUNS, DONE): os.makedirs(p, exist_ok=True)

LLM_MODE = CFG.get("llm_mode","none")
OLLAMA   = CFG.get("ollama", {})
OPENAI   = CFG.get("openai", {})

app = Flask(__name__)
GOAL_LINE = re.compile(r"^- \[.\]\s+([DMY]-\d{3})\s+(.*)$", re.IGNORECASE)
iso = lambda: dt.datetime.now(ZoneInfo("America/Detroit")).isoformat(timespec="seconds")

@app.template_filter("fmt_ts")
def fmt_ts(s):
    # Render ISO date string in America/Detroit like 9/13/2025 5:15 PM
    if not s:
        return "—"
    try:
        d = dt.datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=ZoneInfo("UTC"))
        local = d.astimezone(ZoneInfo("America/Detroit"))
        return local.strftime("%-m/%-d/%Y %-I:%M %p")
    except Exception:
        return s

# ============================================
# OVERTHINKER BLOCK 3: IO Helpers
# ============================================
def read_text(p):
    return open(p,"r",encoding="utf-8").read() if os.path.exists(p) else ""
def write_text(p,s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p,"w",encoding="utf-8").write(s)
def load_json(path, default):
    try: return json.load(open(path,"r",encoding="utf-8"))
    except: return default
def save_json(path, data):
    json.dump(data, open(path,"w",encoding="utf-8"), indent=2)
def read_persona():
    return read_text(PERSONA)

# ============================================
# OVERTHINKER BLOCK 4: Goal Parsing & Files
# ============================================
def parse_master(path, scope):
    out=[]; txt=read_text(path)
    for line in txt.splitlines():
        m=GOAL_LINE.match(line.strip())
        if not m: continue
        gid, title = m.group(1).upper(), m.group(2).strip()
        done = "[x]" in line[:6].lower()
        out.append({"id":gid,"title":title,"scope":scope,"done":done})
    return out

def gpath(gid): return os.path.join(ITEMS, f"{gid}.md")

def ensure_item(g):
    p=gpath(g["id"])
    if os.path.exists(p): return
    write_text(p, f"""# {g['id']} — {g['title']}
- scope: {g['scope']}
- iteration_count: 0
- last_runtime:
- summary: {g['title']}
- created_at: {iso()}

## Original Goal
{g['title']}

## Path to completion
1. Draft plan

## Change Log
- {iso()} — Initialized

## Progress (your notes)
""")

def load_item(gid):
    t=read_text(gpath(gid))
    def meta(tag):
        m=re.search(rf"^- {tag}:\s*(.*)$", t, re.M)
        return m.group(1).strip() if m else ""
    def sec(name):
        m=re.search(rf"## {name}\s*(.+?)(\n## |\Z)", t, re.S)
        return (m.group(1).strip() if m else "")
    steps=[re.sub(r"^\d+\.\s*","",s).strip("-• ").strip() for s in sec("Path to completion").splitlines() if s.strip()]
    clog=[]
    mcl=re.search(r"## Change Log\s*(.+?)\n## Progress", t, re.S)
    if mcl:
        for line in mcl.group(1).strip().splitlines():
            line=line.strip().lstrip("- ").strip()
            parts=line.split(" — ",1)
            if len(parts)==2: clog.append({"ts":parts[0].strip(),"note":parts[1].strip()})
    return {
        "scope": meta("scope") or "daily",
        "id": gid,
        "summary": meta("summary") or sec("Original Goal") or gid,
        "original": sec("Original Goal") or meta("summary"),
        "steps": steps or ["Draft plan"],
        "progress": sec("Progress (your notes)"),
        "iteration_count": int(meta("iteration_count") or "0"),
        "last_runtime": meta("last_runtime"),
        "changelog": clog
    }

def save_item(gid, item):
    lines=[
        f"# {gid} — {item['summary']}",
        f"- scope: {item['scope']}",
        f"- iteration_count: {item['iteration_count']}",
        f"- last_runtime: {item['last_runtime']}",
        f"- summary: {item['summary']}",
        "", "## Original Goal", item["original"], "",
        "## Path to completion"
    ]
    for i,s in enumerate(item["steps"],1): lines.append(f"{i}. {s}")
    lines += ["", "## Change Log"] + [f"- {c['ts']} — {c['note']}" for c in item["changelog"]]
    lines += ["", "## Progress (your notes)", (item["progress"] or "").rstrip()+"\n"]
    write_text(gpath(gid), "\n".join(lines))

# ============================================
# OVERTHINKER BLOCK 5: Rollover Policy (resets)
# ============================================
def settings():
    s=load_json(SETTINGS, {"reset_daily":False,"reset_monthly":False,"reset_yearly":False})
    s.setdefault("reset_daily",False); s.setdefault("reset_monthly",False); s.setdefault("reset_yearly",False)
    return s
def state():
    return load_json(STATE, {"last_daily":"","last_month":"","last_year":""})
def backup_and_reset(header, path, stamp):
    if os.path.exists(path):
        shutil.copyfile(path, os.path.join(RUNS, f"{stamp}_{os.path.basename(path)}"))
    write_text(path, f"# {header}\n")
def maybe_resets():
    s=settings(); st=state(); now=dt.datetime.now(ZoneInfo("America/Detroit"))
    today=now.strftime("%Y-%m-%d"); mon=now.strftime("%Y-%m"); year=now.strftime("%Y")
    changed=False
    if s.get("reset_daily") and st.get("last_daily")!=today:
        backup_and_reset("Daily", DAILY, today); st["last_daily"]=today; changed=True
    if s.get("reset_monthly") and st.get("last_month")!=mon:
        backup_and_reset("Monthly", MONTHLY, mon); st["last_month"]=mon; changed=True
    if s.get("reset_yearly") and st.get("last_year")!=year:
        backup_and_reset("Yearly", YEARLY, year); st["last_year"]=year; changed=True
    if changed: save_json(STATE, st)

# ============================================
# OVERTHINKER BLOCK 6: LLM Refinement (Critique + Revise, Always Improve)
# ============================================
def _build_general_prompt(persona, goal_text, steps, notes):
    return f"""You are a relentless planner that improves goal plans with concrete, lawful steps.

Persona (authoritative context):
{persona}

GOAL (single task):
{goal_text}

CURRENT STEPS:
""" + "\n".join([f"- {s}" for s in steps]) + f"""

PROGRESS NOTES (user-written, truth source):
{notes or '(none)'}

TASK:
1) CRITIQUE: identify 2–5 specific flaws (gaps, sequencing, ambiguity, missing prechecks, lack of timeboxing, unclear “done”).
2) REVISE STEPS: produce an improved plan for the next iteration window only (4–8 steps, each an imperative verb, concrete, testable, timeboxed when appropriate).
3) CHANGES: 1–2 sentences describing how this revision improves the plan.

STRICT OUTPUT FORMAT:
CRITIQUE:
- <bullet 1>
- <bullet 2>
STEPS:
1. <step>
2. <step>
CHANGES:
- <one sentence on improvement>
"""

def _build_cook_prompt(persona, goal_text, steps, notes):
    return f"""You are a no-nonsense cooking coach focused on tonight only.

Persona:
{persona}

GOAL:
{goal_text}

CURRENT STEPS:
""" + "\n".join([f"- {s}" for s in steps]) + f"""

PROGRESS NOTES:
{notes or '(none)'}

RULES:
- Output exactly 6 steps for tonight (25–40 min target), simple cookware, common ingredients.
- No brands, websites, devices, or protein powder unless explicitly in GOAL/NOTES.
- Include precheck (what's on hand), fast prep, cook, a veg, plate, 30–60s postmortem.
- If an ingredient missing, include a simple substitution, not online ordering.

STRICT OUTPUT FORMAT:
CRITIQUE:
- <bullet 1>
- <bullet 2>
STEPS:
1. <step>
2. <step>
3. <step>
4. <step>
5. <step>
6. <step>
CHANGES:
- <one sentence on improvement>
"""

def _parse_sections(text):
    import re
    sec = {"CRITIQUE": "", "STEPS": "", "CHANGES": ""}
    cur = None
    for line in text.splitlines():
        L = line.strip()
        if L.upper().startswith("CRITIQUE:"):
            cur = "CRITIQUE"; continue
        if L.upper().startswith("STEPS:"):
            cur = "STEPS"; continue
        if L.upper().startswith("CHANGES:"):
            cur = "CHANGES"; continue
        if cur:
            sec[cur] += line + "\n"
    steps = []
    for s in sec["STEPS"].splitlines():
        s = s.strip()
        if not s: continue
        s = re.sub(r"^\s*\d+\.\s*","",s)
        s = s.lstrip("-• ").strip()
        if s: steps.append(s)
    reason = ""
    changes_line = next((l.strip("-• ").strip() for l in sec["CHANGES"].splitlines() if l.strip()), "")
    if changes_line:
        reason = changes_line
    else:
        crit_line = next((l.strip("-• ").strip() for l in sec["CRITIQUE"].splitlines() if l.strip()), "")
        reason = crit_line
    return steps, (reason or "Refined for clarity")

def llm_refine(persona, goal_text, steps, notes):
    """Return (new_steps, reason). Always improves (forces tweak on failure)."""
    is_cook = "cook" in (goal_text or "").lower()
    mode = LLM_MODE.lower()

    def _force_improvement(old_steps):
        ns = list(old_steps)
        if len(ns) < 8 and not any("postmortem" in s.lower() or "review" in s.lower() for s in ns):
            ns.append("Do a 60-second postmortem: what worked, what to change next time.")
        elif len(ns) >= 2:
            ns[-2], ns[-1] = ns[-1], ns[-2]
        return ns, "Forced improvement (fallback)"

    if mode == "ollama":
        model = OLLAMA.get("model","llama3.1:8b")
        prompt = _build_cook_prompt(persona, goal_text, steps, notes) if is_cook else _build_general_prompt(persona, goal_text, steps, notes)
        body = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.2, "num_ctx": 4096}}
        try:
            r = requests.post(f"{OLLAMA.get('base_url','http://host.docker.internal:11434')}/api/generate", json=body, timeout=75)
            r.raise_for_status()
            txt = (r.json().get("response","") or "").strip()
            new_steps, reason = _parse_sections(txt)
            if not new_steps or new_steps == steps:
                return _force_improvement(steps)
            return new_steps, (reason or "Refined steps")
        except Exception:
            return _force_improvement(steps)

    elif mode == "openai":
        api = os.environ.get(OPENAI.get("api_key_env","OPENAI_API_KEY"),"")
        if not api:
            return _force_improvement(steps)
        import requests as rq
        msg = _build_cook_prompt(persona, goal_text, steps, notes) if is_cook else _build_general_prompt(persona, goal_text, steps, notes)
        body = {"model": OPENAI.get("model","gpt-4o-mini"),
                "messages":[
                    {"role":"system","content":"Relentless, practical planner. Always critique then revise. Concrete, safe, testable steps."},
                    {"role":"user","content": msg}
                ],
                "temperature": 0.2}
        try:
            r = rq.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {api}"}, json=body, timeout=75)
            r.raise_for_status()
            txt = r.json()["choices"][0]["message"]["content"].strip()
            new_steps, reason = _parse_sections(txt)
            if not new_steps or new_steps == steps:
                return _force_improvement(steps)
            return new_steps, (reason or "Refined steps")
        except Exception:
            return _force_improvement(steps)

    else:
        return _force_improvement(steps)

# ============================================
# OVERTHINKER BLOCK 7: Iteration Engine
# (Tracks a lock file so /status can display "Running since …")
# ============================================
def scan_goals():
    d=parse_master(DAILY,"daily"); m=parse_master(MONTHLY,"monthly"); y=parse_master(YEARLY,"yearly")
    for g in d+m+y: ensure_item(g)
    return d,m,y

def is_done(scope,gid):
    mp={"daily":DAILY,"monthly":MONTHLY,"yearly":YEARLY}
    return bool(re.search(rf"- \[x\]\s+{gid}\b", read_text(mp[scope]), re.I))

def _lock_path():
    return os.path.join(RUNS, "_running.lock.json")

def _write_lock(start_ts):
    try:
        write_text(_lock_path(), json.dumps({"started_at": start_ts}, indent=2))
    except Exception:
        pass

def _clear_lock():
    try:
        p=_lock_path()
        if os.path.exists(p): os.remove(p)
    except Exception:
        pass

def _recent_runs(n=10):
    if not os.path.isdir(RUNS): return []
    files = [f for f in os.listdir(RUNS) if f.endswith(".md")]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(RUNS,x)), reverse=True)
    out=[]
    for f in files[:n]:
        p=os.path.join(RUNS,f)
        ts = dt.datetime.fromtimestamp(os.path.getmtime(p), tz=ZoneInfo("America/Detroit")).isoformat(timespec="seconds")
        out.append({"name": f, "ts": ts})
    return out

def iterate_once():
    maybe_resets()
    start_ts = iso()
    _write_lock(start_ts)
    try:
        persona=read_persona()
        d,m,y=scan_goals()
        today=dt.date.today().isoformat()
        digest=[f"# Run {today}\n"]
        for bucket,label in [(d,"Daily"),(m,"Monthly"),(y,"Yearly")]:
            digest.append(f"## {label}")
            for g in bucket:
                it=load_item(g["id"])
                if g["done"] or is_done(it["scope"], it["id"]):
                    src=gpath(it["id"])
                    if os.path.exists(src):
                        dst=os.path.join(DONE, f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}_{it['id']}.md")
                        shutil.move(src,dst)
                    digest.append(f"- [{g['id']}] {g['title']} — Done (skipped)")
                    continue

                new_steps, reason = llm_refine(persona, it["original"] or it["summary"], it["steps"], it["progress"])
                it["steps"] = new_steps
                it["iteration_count"] = int(it["iteration_count"]) + 1
                it["last_runtime"] = iso()
                note = f"Refined — {reason}"
                it["changelog"].append({"ts": it["last_runtime"], "note": note})
                save_item(it["id"], it)
                digest.append(f"- [{g['id']}] {g['title']} — Iter {it['iteration_count']}: {note}")

        write_text(os.path.join(RUNS, f"{today}-digest.md"), "\n".join(digest))
    finally:
        try:
            t0 = dt.datetime.fromisoformat(start_ts)
            t1 = dt.datetime.now(ZoneInfo("America/Detroit"))
            last_duration_s = int((t1 - t0).total_seconds())
            st = load_json(STATE, {})
            st["last_run_started_at"] = start_ts
            st["last_run_duration_s"] = last_duration_s
            st["last_run_finished_at"] = t1.isoformat(timespec="seconds")
            save_json(STATE, st)
        except Exception:
            pass
        _clear_lock()
# ============================================
# OVERTHINKER BLOCK 8: Web Routes Web Routes
# ============================================
@app.route("/")
def index():
    d,m,y=scan_goals()
    today_disp = dt.datetime.now(ZoneInfo("America/Detroit")).strftime("%-m/%-d/%Y %-I:%M %p")
    return render_template("index.html", title="ASTRA-X Overthinker", today=today_disp, daily=d, monthly=m, yearly=y)

@app.route("/goal/<gid>")
def goal_page(gid):
    return render_template("goal.html", title=gid.upper(), goal=load_item(gid.upper()))

@app.route("/goal/<gid>/save", methods=["POST"])
def goal_save(gid):
    gid=gid.upper()
    it=load_item(gid)
    it["progress"]=request.form.get("progress","")
    done=(request.form.get("done")=="on")
    save_item(gid,it)
    if done:
        src=gpath(gid)
        if os.path.exists(src):
            dst=os.path.join(DONE, f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}_{gid}.md")
            shutil.move(src,dst)
    return redirect(f"/goal/{gid}")

@app.route("/edit", methods=["GET","POST"])
def edit_page():
    if request.method=="POST":
        write_text(DAILY,   (request.form.get("daily","").rstrip()+"\n"))
        write_text(MONTHLY, (request.form.get("monthly","").rstrip()+"\n"))
        write_text(YEARLY,  (request.form.get("yearly","").rstrip()+"\n"))
        s=settings()
        s["reset_daily"]   = ("reset_daily"   in request.form)
        s["reset_monthly"] = ("reset_monthly" in request.form)
        s["reset_yearly"]  = ("reset_yearly"  in request.form)
        save_json(SETTINGS, s)
        return redirect("/")
    s=settings()
    return render_template("edit.html", title="Edit",
        daily_text=read_text(DAILY)   or "# Daily\n- [ ] D-001 ...",
        monthly_text=read_text(MONTHLY) or "# Monthly\n- [ ] M-001 ...",
        yearly_text=read_text(YEARLY) or "# Yearly\n- [ ] Y-001 ...",
        settings=s)

@app.route("/status")
def status_page():
    d,m,y = scan_goals()
    counts = {"daily": len(d), "monthly": len(m), "yearly": len(y)}
    items_count = 0
    goals_snap = []
    try:
        for g in d+m+y:
            items_count += 1
            it = load_item(g["id"])
            goals_snap.append({"id": g["id"], "title": g["title"], "last_runtime": it.get("last_runtime","")})
    except Exception:
        pass
    counts["items"] = items_count

    next_run = None
    try:
        job = SCHEDULER.get_job("iterate")
        if job and job.next_run_time:
            nr = job.next_run_time.astimezone(ZoneInfo("America/Detroit"))
            next_run = nr.strftime("%-m/%-d/%Y %-I:%M %p")
    except Exception:
        next_run = None

    running = os.path.exists(_lock_path())
    running_since = None
    if running:
        try:
            meta = json.loads(read_text(_lock_path()))
            running_since = meta.get("started_at","")
        except Exception:
            pass

    st = load_json(STATE, {})
    last_run = st.get("last_run_finished_at","") or st.get("last_run_started_at","")
    last_duration = st.get("last_run_duration_s", None)

    return render_template("status.html",
        title="Status",
        running=running,
        running_since=running_since,
        next_run=next_run,
        last_run=last_run,
        last_duration=last_duration,
        interval_minutes=int(CFG.get("iteration_interval_minutes",60)),
        llm_mode=LLM_MODE,
        llm_model=OLLAMA.get("model") if LLM_MODE.lower()=="ollama" else (OPENAI.get("model") if LLM_MODE.lower()=="openai" else ""),
        counts=counts,
        recent_runs=_recent_runs(),
        goals=goals_snap)
# ============================================
# OVERTHINKER BLOCK 9: App Boot
# ============================================
if __name__=="__main__":
    global SCHEDULER
    SCHEDULER = BackgroundScheduler()
    SCHEDULER.add_job(iterate_once,"interval",minutes=int(CFG.get("iteration_interval_minutes",60)),id="iterate",max_instances=1,coalesce=True)
    SCHEDULER.start()
    _=scan_goals()
    app.run(host="0.0.0.0", port=7000)
