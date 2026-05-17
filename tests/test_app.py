from __future__ import annotations

import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from overthinker.app import create_app
from overthinker.core.models import GoalItem, Scope
from overthinker.services.llm import LLMCallResult
from overthinker.services.planner import run_iteration
from overthinker.storage.repository import SQLiteRepository


class RepositoryTests(unittest.TestCase):
    def make_db_path(self) -> Path:
        root = Path("data/private/test-work")
        root.mkdir(parents=True, exist_ok=True)
        return root / f"{uuid4().hex}.sqlite3"

    def test_initialize_keeps_new_scopes_empty(self) -> None:
        db_path = self.make_db_path()
        try:
            repository = SQLiteRepository(db_path)
            repository.initialize()

            daily = repository.get_goal_document(Scope.DAILY)
            weekly = repository.get_goal_document(Scope.WEEKLY)

            self.assertEqual(len(daily.items), 0)
            self.assertEqual(len(weekly.items), 0)
        finally:
            db_path.unlink(missing_ok=True)

    def test_run_persists_model_metadata(self) -> None:
        db_path = self.make_db_path()
        try:
            repository = SQLiteRepository(db_path)
            repository.initialize()
            repository.save_goal_document(
                Scope.DAILY,
                [GoalItem(title="Test daily goal", order=0)],
                "",
            )

            record = repository.create_run(
                Scope.DAILY,
                "## Path to Completion\nTest\n\n## Summary\nDone",
                trigger="manual",
                provider="ollama",
                configured_model="configured-model",
                effective_model="effective-model",
            )

            self.assertEqual(record.provider, "ollama")
            self.assertEqual(record.configured_model, "configured-model")
            self.assertEqual(record.effective_model, "effective-model")
            self.assertEqual(len(repository.list_run_sections(record.run_id)), 2)
        finally:
            db_path.unlink(missing_ok=True)


class AppTests(unittest.TestCase):
    def test_root_serves_portfolio_demo(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("ASTRA-X Overthinker", response.text)
            self.assertIn("Iterative Planning Demo", response.text)
            self.assertIn("Task", response.text)
            self.assertIn("feedback", response.text)
            self.assertIn("/ui/overthinker.html", response.text)

    def test_demo_runs_endpoint(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/demo/frozen-runs")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertGreaterEqual(len(payload["runs"]), 2)
            self.assertEqual(payload["runs"][0]["trigger"], "demo playback")

    def test_operations_evidence_endpoint(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/operations/evidence")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("model_router", payload)
            self.assertIn("prompt_registry", payload)
            self.assertIn("guardrails", payload)
            self.assertIn("evaluation_harness", payload)

    def test_static_eval_endpoint(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            response = client.post("/api/evals/run", json={"suite": "planning_basic"})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["failed_count"], 0)

    def test_health_exposes_scope_readiness(self) -> None:
        app = create_app()
        with patch("overthinker.api.routes.fetch_ollama_models", new=AsyncMock(return_value=["qwen2.5:7b-instruct"])):
            with TestClient(app) as client:
                response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("scope_readiness", payload)
        self.assertTrue(any(entry["scope"] == "daily" for entry in payload["scope_readiness"]))


class PlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_iteration_returns_model_metadata(self) -> None:
        root = Path("data/private/test-work")
        root.mkdir(parents=True, exist_ok=True)
        db_path = root / f"{uuid4().hex}.sqlite3"
        try:
            repository = SQLiteRepository(db_path)
            repository.initialize()
            repository.save_goal_document(
                Scope.DAILY,
                [GoalItem(title="Test daily goal", order=0)],
                "",
            )
            with patch(
                "overthinker.services.planner.call_llm",
                new=AsyncMock(
                    return_value=LLMCallResult(
                        content="## Path to Completion\nTest\n\n## Summary\nDone",
                        provider="ollama",
                        configured_model="configured-model",
                        effective_model="effective-model",
                    )
                ),
            ):
                result = await run_iteration(Scope.DAILY, repository=repository)
        finally:
            db_path.unlink(missing_ok=True)

        self.assertEqual(result["provider"], "ollama")
        self.assertEqual(result["configured_model"], "configured-model")
        self.assertEqual(result["effective_model"], "effective-model")


if __name__ == "__main__":
    unittest.main()
