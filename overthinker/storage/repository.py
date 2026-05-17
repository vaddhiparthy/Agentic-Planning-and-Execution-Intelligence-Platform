from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from overthinker.core.models import FeedbackEntry, GoalDocument, GoalItem, RunRecord, Scope
from overthinker.core.paths import DATABASE_FILE
from overthinker.storage.migration import migrate_current_storage


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_run_id(scope: Scope) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    prefix = {
        Scope.DAILY: "D",
        Scope.WEEKLY: "W",
        Scope.YEARLY: "Y",
    }[scope]
    return f"{prefix}-{stamp}"


def summarize_markdown(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:160]
    return "Untitled run"


def split_markdown_sections(markdown: str) -> list[tuple[str, str]]:
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


class SQLiteRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DATABASE_FILE

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS goal_documents (
                    scope TEXT PRIMARY KEY,
                    notes TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS goal_items (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    details TEXT NOT NULL DEFAULT '',
                    priority INTEGER NOT NULL DEFAULT 3,
                    active INTEGER NOT NULL DEFAULT 1,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(scope) REFERENCES goal_documents(scope)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    text TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trigger TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    plan_markdown TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    provider TEXT,
                    configured_model TEXT,
                    effective_model TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    section_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_goal_items_scope_order ON goal_items(scope, order_index)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_scope_created ON feedback(scope, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_scope_status_created ON runs(scope, status, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_sections_run_order ON run_sections(run_id, order_index)"
            )
            self._ensure_run_columns(conn)
            conn.commit()

        migrate_current_storage(self)

    def _ensure_run_columns(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(runs)").fetchall()
        columns = {row["name"] for row in rows}
        for name, sql_type, default in (
            ("trigger", "TEXT", "'manual'"),
            ("provider", "TEXT", "NULL"),
            ("configured_model", "TEXT", "NULL"),
            ("effective_model", "TEXT", "NULL"),
        ):
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE runs ADD COLUMN {name} {sql_type} DEFAULT {default}"
                )

    def _ensure_goal_document(self, scope: Scope) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO goal_documents(scope, notes, updated_at)
                VALUES (?, '', ?)
                ON CONFLICT(scope) DO NOTHING
                """,
                (scope.value, now_iso()),
            )
            conn.commit()

    def get_goal_document(self, scope: Scope) -> GoalDocument:
        self._ensure_goal_document(scope)
        with self.connection() as conn:
            row = conn.execute(
                "SELECT scope, notes, updated_at FROM goal_documents WHERE scope = ?",
                (scope.value,),
            ).fetchone()
            item_rows = conn.execute(
                """
                SELECT id, title, details, priority, active, order_index
                FROM goal_items
                WHERE scope = ?
                ORDER BY order_index ASC, updated_at ASC
                """,
                (scope.value,),
            ).fetchall()

        items = [
            GoalItem(
                id=item["id"],
                title=item["title"],
                details=item["details"],
                priority=int(item["priority"]),
                active=bool(item["active"]),
                order=int(item["order_index"]),
            )
            for item in item_rows
        ]
        return GoalDocument(
            scope=Scope(row["scope"]),
            items=items,
            notes=row["notes"] or "",
            updated_at=row["updated_at"],
        )

    def save_goal_document(self, scope: Scope, items: list[GoalItem], notes: str) -> GoalDocument:
        updated_at = now_iso()
        self._ensure_goal_document(scope)
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE goal_documents
                SET notes = ?, updated_at = ?
                WHERE scope = ?
                """,
                (notes.strip(), updated_at, scope.value),
            )
            conn.execute("DELETE FROM goal_items WHERE scope = ?", (scope.value,))
            for index, item in enumerate(items):
                conn.execute(
                    """
                    INSERT INTO goal_items(
                        id, scope, title, details, priority, active, order_index, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        scope.value,
                        item.title.strip(),
                        item.details.strip(),
                        item.priority,
                        1 if item.active else 0,
                        index,
                        updated_at,
                    ),
                )
            conn.commit()
        return self.get_goal_document(scope)

    def list_feedback(self, scope: Scope, limit: int = 50) -> list[FeedbackEntry]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, scope, created_at, text
                FROM feedback
                WHERE scope = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (scope.value, limit),
            ).fetchall()
        return [FeedbackEntry(**dict(row)) for row in rows]

    def add_feedback(self, scope: Scope, text: str) -> FeedbackEntry:
        entry = FeedbackEntry(scope=scope, created_at=now_iso(), text=text.strip())
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO feedback(id, scope, created_at, text) VALUES (?, ?, ?, ?)",
                (entry.id, entry.scope.value, entry.created_at, entry.text),
            )
            conn.commit()
        return entry

    def _row_to_run_record(self, row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            scope=Scope(row["scope"]),
            status=row["status"],
            trigger=row["trigger"] or "manual",
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            plan_markdown=row["plan_markdown"],
            summary=row["summary"] or "",
            provider=row["provider"],
            configured_model=row["configured_model"],
            effective_model=row["effective_model"],
        )

    def get_current_run(self, scope: Scope) -> RunRecord | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT run_id, scope, status, trigger, created_at, completed_at, plan_markdown, summary,
                       provider, configured_model, effective_model
                FROM runs
                WHERE scope = ? AND status = 'current'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (scope.value,),
            ).fetchone()
        return self._row_to_run_record(row) if row else None

    def list_runs(self, scope: Scope, limit: int = 20) -> list[RunRecord]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT run_id, scope, status, trigger, created_at, completed_at, plan_markdown, summary,
                       provider, configured_model, effective_model
                FROM runs
                WHERE scope = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (scope.value, limit),
            ).fetchall()
        return [self._row_to_run_record(row) for row in rows]

    def create_run(
        self,
        scope: Scope,
        plan_markdown: str,
        *,
        trigger: str = "manual",
        provider: str | None = None,
        configured_model: str | None = None,
        effective_model: str | None = None,
    ) -> RunRecord:
        created_at = now_iso()
        run_id = new_run_id(scope)
        cleaned_markdown = plan_markdown.strip()
        summary = summarize_markdown(cleaned_markdown)
        sections = split_markdown_sections(cleaned_markdown)

        with self.connection() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = 'archived', completed_at = ?
                WHERE scope = ? AND status = 'current'
                """,
                (created_at, scope.value),
            )
            conn.execute(
                """
                INSERT INTO runs(
                    run_id, scope, status, trigger, created_at, completed_at, plan_markdown, summary,
                    provider, configured_model, effective_model
                )
                VALUES (?, ?, 'current', ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    scope.value,
                    trigger,
                    created_at,
                    cleaned_markdown,
                    summary,
                    provider,
                    configured_model,
                    effective_model,
                ),
            )
            for index, (section_name, content) in enumerate(sections):
                conn.execute(
                    """
                    INSERT INTO run_sections(run_id, section_name, content, order_index)
                    VALUES (?, ?, ?, ?)
                    """,
                    (run_id, section_name, content, index),
                )
            conn.commit()

        record = self.get_current_run(scope)
        if record is None:
            raise RuntimeError("Failed to persist current run.")
        return record

    def archive_current_run(self, scope: Scope) -> RunRecord | None:
        current = self.get_current_run(scope)
        if current is None:
            return None
        completed_at = now_iso()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = 'archived', completed_at = ?
                WHERE run_id = ?
                """,
                (completed_at, current.run_id),
            )
            conn.commit()
        rows = self.list_runs(scope, limit=1)
        return rows[0] if rows else None

    def count_runs_today(self, scope: Scope) -> int:
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM runs
                WHERE scope = ? AND created_at >= ? AND created_at < ?
                """,
                (scope.value, start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
            ).fetchone()
        return int(row["count"])

    def list_run_sections(self, run_id: str) -> list[dict[str, str]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT section_name, content
                FROM run_sections
                WHERE run_id = ?
                ORDER BY order_index ASC
                """,
                (run_id,),
            ).fetchall()
        return [{"section_name": row["section_name"], "content": row["content"]} for row in rows]

    def export_storage_snapshot(self) -> dict:
        snapshot: dict[str, object] = {"goals": {}, "feedback": {}, "runs": {}}
        for scope in Scope:
            document = self.get_goal_document(scope)
            snapshot["goals"][scope.value] = document.model_dump(mode="json")
            snapshot["feedback"][scope.value] = [
                entry.model_dump(mode="json") for entry in self.list_feedback(scope, limit=200)
            ]
            snapshot["runs"][scope.value] = [
                run.model_dump(mode="json") for run in self.list_runs(scope, limit=100)
            ]
        return snapshot

    def import_storage_snapshot(self, snapshot: dict) -> None:
        for scope_value, payload in (snapshot.get("goals") or {}).items():
            scope = Scope(scope_value)
            items = [GoalItem(**item) for item in payload.get("items", [])]
            self.save_goal_document(scope, items, payload.get("notes", ""))

        for scope_value, entries in (snapshot.get("feedback") or {}).items():
            scope = Scope(scope_value)
            with self.connection() as conn:
                for entry_payload in reversed(entries):
                    entry = FeedbackEntry(**entry_payload)
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO feedback(id, scope, created_at, text)
                        VALUES (?, ?, ?, ?)
                        """,
                        (entry.id, scope.value, entry.created_at, entry.text),
                    )
                conn.commit()

        for scope_value, runs in (snapshot.get("runs") or {}).items():
            with self.connection() as conn:
                for run_payload in reversed(runs):
                    run = RunRecord(**run_payload)
                    exists = conn.execute(
                        "SELECT 1 FROM runs WHERE run_id = ?",
                        (run.run_id,),
                    ).fetchone()
                    if exists:
                        continue
                    conn.execute(
                        """
                        INSERT INTO runs(
                            run_id, scope, status, trigger, created_at, completed_at, plan_markdown,
                            summary, provider, configured_model, effective_model
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run.run_id,
                            run.scope.value,
                            run.status,
                            run.trigger,
                            run.created_at,
                            run.completed_at,
                            run.plan_markdown,
                            run.summary,
                            run.provider,
                            run.configured_model,
                            run.effective_model,
                        ),
                    )
                    for index, (section_name, content) in enumerate(
                        split_markdown_sections(run.plan_markdown)
                    ):
                        conn.execute(
                            """
                            INSERT INTO run_sections(run_id, section_name, content, order_index)
                            VALUES (?, ?, ?, ?)
                            """,
                            (run.run_id, section_name, content, index),
                        )
                conn.commit()
