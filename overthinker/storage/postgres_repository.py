from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from overthinker.core.config import OverthinkerConfig
from overthinker.core.models import FeedbackEntry, GoalDocument, GoalItem, RunRecord, Scope
from overthinker.storage.repository import (
    new_run_id,
    now_iso,
    split_markdown_sections,
    summarize_markdown,
)


class PostgresRepository:
    def __init__(self, storage_cfg: OverthinkerConfig.StorageConfig):
        self.cfg = storage_cfg
        self.schema = storage_cfg.postgres_schema
        self.prefix = storage_cfg.postgres_table_prefix

    @contextmanager
    def connection(self) -> Iterator:
        conn = psycopg2.connect(
            host=self.cfg.postgres_host,
            port=self.cfg.postgres_port,
            dbname=self.cfg.postgres_database,
            user=self.cfg.postgres_user,
            password=self.cfg.postgres_password,
            cursor_factory=RealDictCursor,
        )
        try:
            yield conn
        finally:
            conn.close()

    def _table(self, suffix: str):
        return sql.Identifier(self.schema, f"{self.prefix}{suffix}")

    def initialize(self) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
                cur.execute(
                    sql.SQL(
                        """
                        CREATE TABLE IF NOT EXISTS {} (
                            scope TEXT PRIMARY KEY,
                            notes TEXT NOT NULL DEFAULT '',
                            updated_at TEXT NOT NULL
                        )
                        """
                    ).format(self._table("goal_documents"))
                )
                cur.execute(
                    sql.SQL(
                        """
                        CREATE TABLE IF NOT EXISTS {} (
                            id TEXT PRIMARY KEY,
                            scope TEXT NOT NULL,
                            title TEXT NOT NULL DEFAULT '',
                            details TEXT NOT NULL DEFAULT '',
                            priority INTEGER NOT NULL DEFAULT 3,
                            active BOOLEAN NOT NULL DEFAULT TRUE,
                            order_index INTEGER NOT NULL DEFAULT 0,
                            updated_at TEXT NOT NULL
                        )
                        """
                    ).format(self._table("goal_items"))
                )
                cur.execute(
                    sql.SQL(
                        """
                        CREATE TABLE IF NOT EXISTS {} (
                            id TEXT PRIMARY KEY,
                            scope TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            text TEXT NOT NULL
                        )
                        """
                    ).format(self._table("feedback"))
                )
                cur.execute(
                    sql.SQL(
                        """
                        CREATE TABLE IF NOT EXISTS {} (
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
                    ).format(self._table("runs"))
                )
                cur.execute(
                    sql.SQL(
                        """
                        CREATE TABLE IF NOT EXISTS {} (
                            id BIGSERIAL PRIMARY KEY,
                            run_id TEXT NOT NULL,
                            section_name TEXT NOT NULL,
                            content TEXT NOT NULL,
                            order_index INTEGER NOT NULL DEFAULT 0
                        )
                        """
                    ).format(self._table("run_sections"))
                )
                cur.execute(
                    sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (scope, order_index)").format(
                        sql.Identifier(f"{self.prefix}goal_items_scope_order_idx"),
                        self._table("goal_items"),
                    )
                )
                cur.execute(
                    sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (scope, created_at DESC)").format(
                        sql.Identifier(f"{self.prefix}feedback_scope_created_idx"),
                        self._table("feedback"),
                    )
                )
                cur.execute(
                    sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (scope, status, created_at DESC)").format(
                        sql.Identifier(f"{self.prefix}runs_scope_status_created_idx"),
                        self._table("runs"),
                    )
                )
                cur.execute(
                    sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (run_id, order_index)").format(
                        sql.Identifier(f"{self.prefix}run_sections_run_order_idx"),
                        self._table("run_sections"),
                    )
                )
            conn.commit()

    def _ensure_goal_document(self, scope: Scope) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}(scope, notes, updated_at)
                        VALUES (%s, '', %s)
                        ON CONFLICT(scope) DO NOTHING
                        """
                    ).format(self._table("goal_documents")),
                    (scope.value, now_iso()),
                )
            conn.commit()

    def get_goal_document(self, scope: Scope) -> GoalDocument:
        self._ensure_goal_document(scope)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT scope, notes, updated_at FROM {} WHERE scope = %s").format(
                        self._table("goal_documents")
                    ),
                    (scope.value,),
                )
                row = cur.fetchone()
                cur.execute(
                    sql.SQL(
                        """
                        SELECT id, title, details, priority, active, order_index
                        FROM {}
                        WHERE scope = %s
                        ORDER BY order_index ASC, updated_at ASC
                        """
                    ).format(self._table("goal_items")),
                    (scope.value,),
                )
                item_rows = cur.fetchall()
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
        return GoalDocument(scope=Scope(row["scope"]), items=items, notes=row["notes"] or "", updated_at=row["updated_at"])

    def save_goal_document(self, scope: Scope, items: list[GoalItem], notes: str) -> GoalDocument:
        updated_at = now_iso()
        self._ensure_goal_document(scope)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("UPDATE {} SET notes = %s, updated_at = %s WHERE scope = %s").format(
                        self._table("goal_documents")
                    ),
                    (notes.strip(), updated_at, scope.value),
                )
                cur.execute(
                    sql.SQL("DELETE FROM {} WHERE scope = %s").format(self._table("goal_items")),
                    (scope.value,),
                )
                for index, item in enumerate(items):
                    cur.execute(
                        sql.SQL(
                            """
                            INSERT INTO {}(
                                id, scope, title, details, priority, active, order_index, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """
                        ).format(self._table("goal_items")),
                        (
                            item.id,
                            scope.value,
                            item.title.strip(),
                            item.details.strip(),
                            item.priority,
                            item.active,
                            index,
                            updated_at,
                        ),
                    )
            conn.commit()
        return self.get_goal_document(scope)

    def list_feedback(self, scope: Scope, limit: int = 50) -> list[FeedbackEntry]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """
                        SELECT id, scope, created_at, text
                        FROM {}
                        WHERE scope = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """
                    ).format(self._table("feedback")),
                    (scope.value, limit),
                )
                rows = cur.fetchall()
        return [FeedbackEntry(**dict(row)) for row in rows]

    def add_feedback(self, scope: Scope, text: str) -> FeedbackEntry:
        entry = FeedbackEntry(scope=scope, created_at=now_iso(), text=text.strip())
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("INSERT INTO {}(id, scope, created_at, text) VALUES (%s, %s, %s, %s)").format(
                        self._table("feedback")
                    ),
                    (entry.id, entry.scope.value, entry.created_at, entry.text),
                )
            conn.commit()
        return entry

    def _row_to_run_record(self, row) -> RunRecord:
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
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """
                        SELECT run_id, scope, status, trigger, created_at, completed_at, plan_markdown, summary,
                               provider, configured_model, effective_model
                        FROM {}
                        WHERE scope = %s AND status = 'current'
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ).format(self._table("runs")),
                    (scope.value,),
                )
                row = cur.fetchone()
        return self._row_to_run_record(row) if row else None

    def list_runs(self, scope: Scope, limit: int = 20) -> list[RunRecord]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """
                        SELECT run_id, scope, status, trigger, created_at, completed_at, plan_markdown, summary,
                               provider, configured_model, effective_model
                        FROM {}
                        WHERE scope = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """
                    ).format(self._table("runs")),
                    (scope.value, limit),
                )
                rows = cur.fetchall()
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
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "UPDATE {} SET status = 'archived', completed_at = %s WHERE scope = %s AND status = 'current'"
                    ).format(self._table("runs")),
                    (created_at, scope.value),
                )
                cur.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}(
                            run_id, scope, status, trigger, created_at, completed_at, plan_markdown, summary,
                            provider, configured_model, effective_model
                        ) VALUES (%s, %s, 'current', %s, %s, NULL, %s, %s, %s, %s, %s)
                        """
                    ).format(self._table("runs")),
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
                    cur.execute(
                        sql.SQL(
                            "INSERT INTO {}(run_id, section_name, content, order_index) VALUES (%s, %s, %s, %s)"
                        ).format(self._table("run_sections")),
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
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("UPDATE {} SET status = 'archived', completed_at = %s WHERE run_id = %s").format(
                        self._table("runs")
                    ),
                    (completed_at, current.run_id),
                )
            conn.commit()
        rows = self.list_runs(scope, limit=1)
        return rows[0] if rows else None

    def count_runs_today(self, scope: Scope) -> int:
        from datetime import datetime, timedelta

        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "SELECT COUNT(*) AS count FROM {} WHERE scope = %s AND created_at >= %s AND created_at < %s"
                    ).format(self._table("runs")),
                    (scope.value, start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
                )
                row = cur.fetchone()
        return int(row["count"])

    def list_run_sections(self, run_id: str) -> list[dict[str, str]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "SELECT section_name, content FROM {} WHERE run_id = %s ORDER BY order_index ASC"
                    ).format(self._table("run_sections")),
                    (run_id,),
                )
                rows = cur.fetchall()
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
            for entry_payload in reversed(entries):
                entry = FeedbackEntry(**entry_payload)
                with self.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            sql.SQL(
                                """
                                INSERT INTO {}(id, scope, created_at, text)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (id) DO NOTHING
                                """
                            ).format(self._table("feedback")),
                            (entry.id, scope.value, entry.created_at, entry.text),
                        )
                    conn.commit()

        for scope_value, runs in (snapshot.get("runs") or {}).items():
            for run_payload in reversed(runs):
                run = RunRecord(**run_payload)
                with self.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            sql.SQL("SELECT 1 AS exists FROM {} WHERE run_id = %s").format(
                                self._table("runs")
                            ),
                            (run.run_id,),
                        )
                        if cur.fetchone():
                            conn.commit()
                            continue
                        cur.execute(
                            sql.SQL(
                                """
                                INSERT INTO {}(
                                    run_id, scope, status, trigger, created_at, completed_at, plan_markdown,
                                    summary, provider, configured_model, effective_model
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (run_id) DO NOTHING
                                """
                            ).format(self._table("runs")),
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
                        for index, section in enumerate(split_markdown_sections(run.plan_markdown)):
                            cur.execute(
                                sql.SQL(
                                    "INSERT INTO {}(run_id, section_name, content, order_index) VALUES (%s, %s, %s, %s)"
                                ).format(self._table("run_sections")),
                                (run.run_id, section[0], section[1], index),
                            )
                    conn.commit()
