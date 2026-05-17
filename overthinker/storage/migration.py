from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from overthinker.core.models import GoalItem, Scope
from overthinker.core.paths import (
    LEGACY_FEEDBACK_DIR,
    LEGACY_GOALS_DIR,
    LEGACY_RUNS_CURRENT_DIR,
    LEGACY_RUNS_PAST_DIR,
)
GOAL_LINE_RE = re.compile(r"^(?:[-*]|\d+\.)\s+(?P<title>.+)$")
RUN_HEADER_RE = re.compile(r"#\s+\w+\s+[^\w]?\s+(?P<run_id>[A-Z]-\d+)")
TIMESTAMP_RE = re.compile(r"^\[(?P<ts>[^\]]+)\]$")


def _split_markdown_sections(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = "Plan"
    current_lines: list[str] = []

    def flush() -> None:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_title, content))

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip() or "Plan"
            current_lines = []
            continue
        current_lines.append(line)
    flush()
    return sections


def _parse_goal_markdown(text: str) -> tuple[list[GoalItem], str]:
    items: list[GoalItem] = []
    notes: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = GOAL_LINE_RE.match(stripped)
        if match:
            items.append(GoalItem(title=match.group("title").strip(), order=len(items)))
            continue
        notes.append(stripped)
    return items, "\n".join(notes).strip()


def _parse_feedback_markdown(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    current_ts = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_ts and current_lines:
            entries.append((current_ts, "\n".join(current_lines).strip()))

    for line in text.splitlines():
        match = TIMESTAMP_RE.match(line.strip())
        if match:
            flush()
            current_ts = match.group("ts")
            current_lines = []
            continue
        if line.strip():
            current_lines.append(line.rstrip())
    flush()
    return entries


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _extract_run_id(path: Path, text: str) -> str:
    match = RUN_HEADER_RE.search(text)
    if match:
        return match.group("run_id")
    return path.stem


def _goal_documents_populated(repository) -> bool:
    with repository.connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM goal_items").fetchone()
    return int(row["count"]) > 0


def _feedback_populated(repository) -> bool:
    with repository.connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM feedback").fetchone()
    return int(row["count"]) > 0


def _runs_populated(repository) -> bool:
    with repository.connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()
    return int(row["count"]) > 0


def _migrate_goal_blobs(repository) -> None:
    with repository.connection() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "goals" not in tables:
            return
        rows = conn.execute(
            "SELECT scope, items_json, notes FROM goals ORDER BY scope"
        ).fetchall()

    for row in rows:
        items = []
        for index, raw_item in enumerate(json.loads(row["items_json"] or "[]")):
            item = GoalItem(**raw_item)
            items.append(item.model_copy(update={"order": index}))
        repository.save_goal_document(Scope(row["scope"]), items, row["notes"] or "")


def _migrate_markdown_goals(repository) -> None:
    for scope in Scope:
        legacy_goal = _read_text(LEGACY_GOALS_DIR / f"{scope.value}.md")
        if not legacy_goal:
            continue
        document = repository.get_goal_document(scope)
        if document.items:
            continue
        items, notes = _parse_goal_markdown(legacy_goal)
        repository.save_goal_document(scope, items, notes)


def _migrate_feedback_markdown(repository) -> None:
    for scope in Scope:
        legacy_feedback = _read_text(LEGACY_FEEDBACK_DIR / f"{scope.value}.md")
        for ts, text in _parse_feedback_markdown(legacy_feedback):
            entry = repository.add_feedback(scope, text)
            with repository.connection() as conn:
                conn.execute(
                    "UPDATE feedback SET created_at = ? WHERE id = ?",
                    (ts, entry.id),
                )
                conn.commit()


def _migrate_run_markdown(repository) -> None:
    with repository.connection() as conn:
        existing_run_ids = {
            row["run_id"] for row in conn.execute("SELECT run_id FROM runs").fetchall()
        }

    for scope in Scope:
        for directory, status in (
            (LEGACY_RUNS_PAST_DIR, "archived"),
            (LEGACY_RUNS_CURRENT_DIR, "current"),
        ):
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.md")):
                if not path.name.lower().startswith(scope.value[0]):
                    continue
                text = _read_text(path)
                if not text:
                    continue
                run_id = _extract_run_id(path, text)
                if run_id in existing_run_ids:
                    continue
                created_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat(
                    timespec="seconds"
                )
                with repository.connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO runs(
                            run_id, scope, status, trigger, created_at, completed_at,
                            plan_markdown, summary, provider, configured_model, effective_model
                        ) VALUES (?, ?, ?, 'manual', ?, ?, ?, ?, NULL, NULL, NULL)
                        """,
                        (
                            run_id,
                            scope.value,
                            status,
                            created_at,
                            None,
                            text,
                            path.stem,
                        ),
                    )
                    conn.commit()
                existing_run_ids.add(run_id)


def _backfill_run_sections(repository) -> None:
    with repository.connection() as conn:
        runs = conn.execute(
            "SELECT run_id, plan_markdown FROM runs ORDER BY created_at ASC"
        ).fetchall()
        existing = {
            row["run_id"]
            for row in conn.execute("SELECT DISTINCT run_id FROM run_sections").fetchall()
        }
        for run in runs:
            if run["run_id"] in existing:
                continue
            for index, (section_name, content) in enumerate(
                _split_markdown_sections(run["plan_markdown"] or "")
            ):
                conn.execute(
                    """
                    INSERT INTO run_sections(run_id, section_name, content, order_index)
                    VALUES (?, ?, ?, ?)
                    """,
                    (run["run_id"], section_name, content, index),
                )
        conn.commit()


def migrate_current_storage(repository) -> None:
    if not _goal_documents_populated(repository):
        _migrate_goal_blobs(repository)
        _migrate_markdown_goals(repository)

    if not _feedback_populated(repository):
        _migrate_feedback_markdown(repository)

    if not _runs_populated(repository):
        _migrate_run_markdown(repository)

    _backfill_run_sections(repository)
