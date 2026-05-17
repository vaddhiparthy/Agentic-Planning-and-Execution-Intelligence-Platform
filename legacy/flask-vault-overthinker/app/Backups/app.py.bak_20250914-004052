# app.py — stable Progress append, robust parse, short changelog
import os, re, json, shutil, datetime as dt
from flask import Flask, render_template, request, redirect, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import yaml, requests
from zoneinfo import ZoneInfo

# ---------- Config ----------
with open("config.yaml","r", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

ROOT = CFG["vault_root"].replace("\\","/")
DAILY = os.path.join(ROOT, CFG["daily_file"])
MONTHLY = os.path.join(ROOT, CFG["monthly_file"])
YEARLY = os.path.join(ROOT, CFG["yearly_file"])
ITEMS = os.path.join(ROOT, CFG["items_dir"])
RUNS  = os.path.join(ROOT, CFG["runs_dir"])
DONE  = os.path.join(ROOT, CFG["done_dir"])
PERSONA = os.path.join(ROOT, "persona.md")

for p in (ITEMS,RUNS,DONE): os.makedirs(p, exist_ok=True)

LLM_MODE = (CFG.get("llm_mode","none") or "none").lower()
OLLAMA = CFG.get("ollama", {})
OPENAI = CFG.get("openai", {})

ET = ZoneInfo("America/Detroit")

app = Flask(__name__)
SCHEDULER = None

# ---------- Helpers ----------
GOAL_LINE = re.compile(r"^- \[(?: |x)\]\s+([DMY]-\d{3})\s+(.*)$", re.I)

def iso_now():
    return dt.datetime.now(ET).isoformat(timespec="seconds")

def fmt_ts(s):
    try:
        t = dt.datetime.fromisoformat(s)
        if not t.tzinfo: t = t.replace(tzinfo=ET)
        return t.astimezone(ET).strftime("%-m/%-d/%Y %-I:%M %p")
    except Exception:
        return s or "—"

@app.template_filter("fmt_ts")
def jinja_fmt_ts(s): return fmt_ts(s)

def read_text(p):
    return open(p,"r",encoding="utf-8").read() if os.path.exists(p) else ""

def write_text(p,s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p,"w",encoding="utf-8") as f: f.write(s)

def parse_master(path, scope, hide_done=True):
    out=[]
    for line in read_text(path).splitlines():
        m = GOAL_LINE.match(line.strip())
        if not m: continue
        gid, title = m.group(1).upper(), m.group(2).strip()
        done = "[x]" in line[:6].lower()
        if hide_done and done: 
            continue
        out.append({"id":gid,"title":title,"scope":scope,"done":done})
    return out

def goal_file(gid): 
    return os.path.join(ITEMS, f"{gid}.md")

def ensure_item(g, initial_progress=None):
    p = goal_file(g["id"])
    if os.path.exists(p): return
    now = iso_now()
    template = f"""# {g['id']} — {g['title']}
- scope: {g['scope']}
- iteration_count: 0
- last_runtime:
- summary: {g['title']}

## Original Goal
{g['title']}

## Path to completion
1. Draft plan

## Change Log
- {now} — Initialized

## Progress (your notes)
{(initial_progress or "").strip()}
"""
    write_text(p, template)

def _extract_section_any(t, names):
    # Try exact names first
    for name in names:
        m = re.search(rf"##\s*{re.escape(name)}\s*(.+?)(\n## |\Z)", t, re.S | re.I)
        if m: 
            return (m.group(1) or "").strip()
    # Fallback for any '## Progress...' variant
    if any(n.lower().startswith("progress") for n in names):
        m = re.search(r"##\s*Progress[^\n]*\n(.+)", t, re.S | re.I)
        if m: 
            return (m.group(1) or "").strip()
    return ""

def load_item(gid):
    t = read_text(goal_file(gid))
    def meta(tag):
        m = re.search(rf"^- {tag}:\s*(.*)$", t, re.M)
        return m.group(1).strip() if m else ""

    original = _extract_section_any(t, ["Original Goal"])
    steps_sec = _extract_section_any(t, ["Path to completion"])

    steps=[]
    for raw in (steps_sec.splitlines() if steps_sec else []):
        s = raw.strip()
        if not s: continue
        s = re.sub(r"^\d+\.\s*","",s)
        s = s.lstrip("-•* ").strip()
        if s: steps.append(s)
    if not steps: steps=["Draft plan"]

    progress = _extract_section_any(t, ["Progress (your notes)", "Progress"])

    clog=[]
    # tolerate either "## Change Log" followed by "## Progress" or EOF
    mcl = re.search(r"##\s*Change Log\s*(.+?)(\n##\s*Progress|\Z)", t, re.S | re.I)
    if mcl:
        for line in mcl.group(1).strip().splitlines():
            line=line.strip().lstrip("- ").strip()
            parts=line.split(" — ",1)
            if len(parts)==2: clog.append({"ts":parts[0].strip(),"note":parts[1].strip()})

    return {
        "scope": meta("scope") or "daily",
        "id": gid,
        "summary": meta("summary") or original or gid,
        "original": original or meta("summary"),
        "steps": steps,
        "progress": progress,
        "iteration_count": int(meta("iteration_count") or "0"),
        "last_runtime": meta("last_runtime"),
        "changelog": clog
    }

def save_item(gid, item):
    lines=[]
    lines.append(f"# {gid} — {item['summary']}")
    lines.append(f"- scope: {item['scope']}")
    lines.append(f"- iteration_count: {item['iteration_count']}")
    lines.append(f"- last_runtime: {item['last_runtime']}")
    lines.append(f"- summary: {item['summary']}")
    lines.append("")
    lines.append("## Original Goal")
    lines.append(item["original"])
    lines.append("")
    lines.append("## Path to completion")
    for i,s in enumerate(item["steps"],1): 
        lines.append(f"{i}. {s}")
    lines.append("")
    lines.append("## Change Log")
    for c in item["changelog"]: 
        lines.append(f"- {c['ts']} — {c['note']}")
    lines.append("")
    lines.append("## Progress (your notes)")
    lines.append((item["progress"] or "").rstrip()+"\n")
    write_text(goal_file(gid), "\n".join(lines))

def read_persona(): 
    return read_text(PERSONA)

def next_id(scope):
    pattern = {"daily":"D","monthly":"M","yearly":"Y"}[scope]
    nums=[]
    for name in os.listdir(ITEMS):
        if not name.endswith(".md"): continue
        m=re.match(rf"({pattern})-(\d{{3}})\.md$", name, re.I)
        if m: nums.append(int(m.group(2)))
    return f"{pattern}-{(max(nums) if nums else 0)+1:03d}"

def link_steps(steps, gid):
    return steps

# ---------- LLM ----------
def _summarize_diff(old_steps, new_steps):
    # Tiny heuristic: find first significant change to summarize
    if new_steps != old_steps:
        added = [s for s in new_steps if s not in old_steps]
        removed = [s for s in old_steps if s not in new_steps]
        if added and removed:
            return "Replaced steps for clarity"
        if added:
            return ("Added: " + (added[0][:40] + ("…" if len(added[0])>40 else "")))[:60]
        if removed:
            return "Removed redundant step"
    return "Grounded refinement"

def _strong_notes(progress_text, head_lines=5, tail_chars=1500):
    lines = [ln for ln in (progress_text or "").splitlines() if ln.strip()]
    head = "\n".join(lines[-head_lines:])  # most recent lines (at end)
    body = progress_text[-tail_chars:] if progress_text else ""
    return head, body

def llm_refine(persona, goal_text, current_steps, progress_notes):
    """
    Ask model to return two sections:
    STEPS:
    <one step per line, 4-8 lines>
    SUMMARY:
    <<=6 words>
    """
    head, body = _strong_notes(progress_notes)
    prompt = f"""Persona:
{persona}

You are a tough, practical critic. Improve the plan.

Rules:
- Be concrete, lawful, realistic. No irrelevant tech (e.g., no NAS/backup for cooking).
- Consider the user's latest notes first (see 'Recent notes'), then full notes.
- Prefer 4–8 steps total. No hallucinations. Avoid brand spam.
- Remove done/obsolete steps; add only necessary next actions.

Goal:
{goal_text}

Current steps:
{chr(10).join(current_steps)}

Recent notes (most recent first):
{head or "(none)"}

All notes (truncated):
{body or "(none)"}

Return exactly:
STEPS:
<one step per line>
SUMMARY:
<<=6 words about what changed>
"""

    def parse_output(txt):
        steps, summary = current_steps, "Grounded refinement"
        if not txt: 
            return steps, summary
        m = re.search(r"STEPS:\s*(.+?)\nSUMMARY:\s*(.+)\Z", txt.strip(), re.S | re.I)
        if m:
            raw_steps = [re.sub(r"^\d+\.\s*","",s).strip("-•* ").strip()
                         for s in m.group(1).strip().splitlines() if s.strip()]
            steps = raw_steps or current_steps
            summary = m.group(2).strip()
            summary = summary[:60] if summary else "Grounded refinement"
        else:
            # fallback: just split lines
            raw = [re.sub(r"^\d+\.\s*","",s).strip("-•* ").strip()
                   for s in txt.splitlines() if s.strip()]
            steps = raw or current_steps
            summary = _summarize_diff(current_steps, steps)
        return steps, summary

    try:
        if LLM_MODE == "ollama":
            url = f"{OLLAMA.get('base_url','http://host.docker.internal:11434')}/api/generate"
            r = requests.post(url, json={"model": OLLAMA.get("model","llama3.1:8b"),
                                         "prompt": prompt, "stream": False}, timeout=120)
            r.raise_for_status()
            txt = r.json().get("response","").strip()
            return parse_output(txt)
        elif LLM_MODE == "openai":
            api = os.environ.get(OPENAI.get("api_key_env","OPENAI_API_KEY"),"")
            if not api: 
                return current_steps, "LLM key missing"
            headers = {"Authorization": f"Bearer {api}"}
            body = {"model": OPENAI.get("model","gpt-4o-mini"),
                    "messages":[
                      {"role":"system","content":"You write concrete, safe, non-hallucinated steps."},
                      {"role":"user","content": prompt}
                    ]}
            r = requests.post("https://api.openai.com/v1/chat/completions",
                              headers=headers, json=body, timeout=120)
            r.raise_for_status()
            txt = r.json()["choices"][0]["message"]["content"].strip()
            return parse_output(txt)
        else:
            return current_steps, "LLM disabled"
    except Exception:
        return current_steps, "Model error (kept prior)"

def is_checked_done(scope, gid):
    mp={"daily":DAILY,"monthly":MONTHLY,"yearly":YEARLY}
    return bool(re.search(rf"- \[x\]\s+{gid}\b", read_text(mp[scope]), re.I))

def mark_master_done(scope, gid):
    file_map = {"daily":DAILY, "monthly":MONTHLY, "yearly":YEARLY}
    path = file_map.get(scope.lower())
    if not path: return
    txt = read_text(path)
    pat = rf"(?m)^-\s*\[\s*\]\s+{gid}\b(.*)$"
    repl = rf"- [x] {gid}\1"
    new_txt = re.sub(pat, repl, txt)
    if new_txt != txt:
        write_text(path, new_txt)

# ---------- Iteration loop ----------
def scan_goals():
    d=parse_master(DAILY,"daily",hide_done=True)
    m=parse_master(MONTHLY,"monthly",hide_done=True)
    y=parse_master(YEARLY,"yearly",hide_done=True)
    for g in d+m+y: ensure_item(g)
    return d,m,y

def iterate_once():
    persona = read_persona()
    d,m,y = scan_goals()
    today = dt.date.today().isoformat()
    digest = [f"# Run {today}\n"]
    for bucket,label in [(d,"Daily"),(m,"Monthly"),(y,"Yearly")]:
        digest.append(f"## {label}")
        for g in bucket:
            it = load_item(g["id"])
            if is_checked_done(it["scope"], it["id"]):
                src = goal_file(it["id"])
                if os.path.exists(src):
                    dst = os.path.join(DONE, f"{dt.datetime.now(ET).strftime('%Y%m%d-%H%M%S')}_{it['id']}.md")
                    shutil.move(src, dst)
                digest.append(f"- [{g['id']}] {g['title']} — Done (archived)")
                continue

            old_steps = it["steps"][:]
            new_steps, reason = llm_refine(
                persona,
                it["original"] or it["summary"],
                it["steps"],
                it["progress"]
            )
            it["steps"] = link_steps(new_steps, it["id"])
            it["iteration_count"] = int(it["iteration_count"])+1
            it["last_runtime"] = iso_now()
            # short 4–6 words summary (use reason, else tiny diff)
            short = (reason or _summarize_diff(old_steps, it["steps"]))
            if len(short) > 60: short = short[:60]
            it["changelog"].append({"ts": it["last_runtime"], "note": short})
            save_item(it["id"], it)
            digest.append(f"- [{g['id']}] {g['title']} — Iter {it['iteration_count']}: {short}")
    write_text(os.path.join(RUNS, f"{today}-digest.md"), "\n".join(digest))

# ---------- Web ----------
@app.route("/")
def index():
    d,m,y = scan_goals()
    return render_template("index.html",
        title="ASTRA-X Overthinker",
        today=dt.date.today().strftime("%-m/%-d/%Y"),
        daily=d, monthly=m, yearly=y)

@app.route("/goal/<gid>")
def goal_page(gid):
    item = load_item(gid.upper())
    return render_template("goal.html", title=f"{gid.upper()}", goal=item)

@app.route("/goal/<gid>/append", methods=["POST"])
def goal_append(gid):
    gid = gid.upper()
    it = load_item(gid)
    append_text = (request.form.get("append_text","") or "").strip()
    if append_text:
        stamp = dt.datetime.now(ET).strftime("%-m/%-d/%Y %-I:%M %p")
        divider = "\n····························\n"
        prior = (it.get("progress","") or "")
        it["progress"] = (prior.rstrip() + ("\n\n" if prior.strip() else "") + f"[{stamp} ET] {append_text}" + divider)
        save_item(gid, it)

    done = (request.form.get("done") == "on")
    if done:
        try:
            mark_master_done(it.get("scope","daily"), gid)
        except Exception:
            pass
        src = goal_file(gid)
        if os.path.exists(src):
            dst = os.path.join(DONE, f"{dt.datetime.now(ET).strftime('%Y%m%d-%H%M%S')}_{gid}.md")
            shutil.move(src, dst)

    # Force reload from markdown (cache-bust)
    return redirect(f"/goal/{gid}?t={int(dt.datetime.now(ET).timestamp())}")

# APIs
@app.route("/api/scheduler/status", methods=["GET"])
def api_scheduler_status():
    job = SCHEDULER.get_job("iterate") if SCHEDULER else None
    enabled = bool(job and (job.next_run_time is not None))
    try:
        nrt = job.next_run_time.astimezone(ET).strftime("%-m/%-d/%Y %-I:%M %p") if job and job.next_run_time else "—"
    except Exception:
        nrt = "—"
    return {"enabled": enabled, "next_run": nrt}

@app.route("/api/run_once", methods=["POST"])
def api_run_once():
    iterate_once()
    return {"ok": True, "ran": True, "ts": dt.datetime.now(ET).strftime("%-m/%-d/%Y %-I:%M %p")}

# ---------- Boot ----------
@app.route("/quickadd/<scope>", methods=["POST"])
def quickadd(scope):
    scope = (scope or "").lower()
    if scope not in ("daily","monthly","yearly"):
        return "bad scope", 400
    lines = (request.form.get("lines","") or "").splitlines()
    file_map = {"daily":DAILY,"monthly":MONTHLY,"yearly":YEARLY}
    master = read_text(file_map[scope]) or f"# {scope.capitalize()}\n"
    for raw in lines:
        text = raw.strip()
        if not text: 
            continue
        m = re.match(r"^\\s*([DMY]-\\d{3})\\s+(.*)$", text, re.I)
        if m:
            gid, title = m.group(1).upper(), m.group(2).strip()
        else:
            gid = next_id(scope)
            title = text
        master += f"- [ ] {gid} {title}\n"
        ensure_item({"id":gid,"title":title,"scope":scope}, initial_progress=raw.strip())
    write_text(file_map[scope], master)
    return redirect("/")

if __name__ == "__main__":
    SCHEDULER = BackgroundScheduler()
    SCHEDULER.add_job(
        iterate_once,
        "interval",
        minutes=int(CFG.get("iteration_interval_minutes", 15)),
        id="iterate",
        max_instances=1,
        coalesce=True
    )
    SCHEDULER.start()
    _ = scan_goals()
    app.run(host="0.0.0.0", port=7000)

