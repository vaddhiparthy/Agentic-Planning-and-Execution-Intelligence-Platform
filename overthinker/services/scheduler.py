from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta

from overthinker.core.config import OverthinkerConfig, load_config
from overthinker.core.models import SchedulerSnapshot
from overthinker.services.planner import run_iteration


class OverthinkerScheduler:
    def __init__(self, repository):
        self.repository = repository
        self.cfg: OverthinkerConfig | None = None
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self.last_run_at: str | None = None
        self.last_error: str | None = None
        self.next_run_at: str | None = None

    def _parse_quiet_hours(self, value: str) -> tuple[time, time]:
        try:
            start, end = value.split("-", maxsplit=1)
            h1, m1 = [int(part) for part in start.split(":")]
            h2, m2 = [int(part) for part in end.split(":")]
            return time(h1, m1), time(h2, m2)
        except Exception:
            return time(2, 0), time(4, 0)

    def _in_quiet_hours(self, cfg: OverthinkerConfig) -> bool:
        current = datetime.now().time()
        start, end = self._parse_quiet_hours(cfg.schedule.quiet_hours)
        if start < end:
            return start <= current <= end
        return current >= start or current <= end

    async def _run_cycle(self) -> None:
        cfg = self.cfg or load_config()
        if self._in_quiet_hours(cfg):
            self.last_error = None
            return

        for scope in cfg.schedule.scopes:
            if self.repository.count_runs_today(scope) >= cfg.schedule.rate_limit_per_day:
                continue
            try:
                await run_iteration(scope, cfg, self.repository, trigger="scheduler")
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)
        self.last_run_at = datetime.now().isoformat(timespec="seconds")

    async def _loop(self) -> None:
        cfg = self.cfg or load_config()
        if cfg.schedule.run_on_startup:
            await self._run_cycle()

        while not self._stop_event.is_set():
            self.cfg = load_config()
            delay = self.cfg.schedule.interval_seconds
            next_run = datetime.now() + timedelta(seconds=delay)
            self.next_run_at = next_run.isoformat(timespec="seconds")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                break
            except asyncio.TimeoutError:
                await self._run_cycle()
        self.next_run_at = None

    async def start(self) -> None:
        self.cfg = load_config()
        if not self.cfg.schedule.autopilot or self._task:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._loop(), name="overthinker-scheduler")

    async def reload(self) -> None:
        await self.shutdown()
        await self.start()

    async def shutdown(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            self.next_run_at = None

    def snapshot(self) -> SchedulerSnapshot:
        cfg = self.cfg or load_config()
        return SchedulerSnapshot(
            running=self._task is not None and not self._task.done(),
            autopilot=cfg.schedule.autopilot,
            hourly_iterations=cfg.schedule.hourly_iterations,
            interval_seconds=cfg.schedule.interval_seconds,
            interval_minutes=round(cfg.schedule.interval_seconds / 60, 2),
            configured_scopes=cfg.schedule.scopes,
            next_run_at=self.next_run_at,
            last_run_at=self.last_run_at,
            last_error=self.last_error,
        )
