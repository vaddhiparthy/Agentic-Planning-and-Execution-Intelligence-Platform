from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Scope(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    YEARLY = "yearly"


class GoalItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str = ""
    details: str = ""
    priority: int = Field(default=3, ge=1, le=5)
    active: bool = True
    order: int = 0


class GoalDocument(BaseModel):
    scope: Scope
    items: list[GoalItem] = Field(default_factory=list)
    notes: str = ""
    updated_at: str | None = None


class FeedbackEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    scope: Scope
    created_at: str
    text: str


class RunRecord(BaseModel):
    run_id: str
    scope: Scope
    status: Literal["current", "archived"]
    trigger: Literal["manual", "scheduler", "bootstrap"] = "manual"
    created_at: str
    completed_at: str | None = None
    plan_markdown: str
    summary: str = ""
    provider: str | None = None
    configured_model: str | None = None
    effective_model: str | None = None


class SchedulerSnapshot(BaseModel):
    running: bool
    autopilot: bool
    hourly_iterations: int
    interval_seconds: int
    interval_minutes: float
    configured_scopes: list[Scope]
    next_run_at: str | None = None
    last_run_at: str | None = None
    last_error: str | None = None
