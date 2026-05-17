from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from .models import Scope
from .paths import CONFIG_DIR, CONFIG_FILE


class ModelConfig(BaseModel):
    provider: str = "ollama"
    model_name: str = "qwen2.5:7b-instruct"
    api_base: str | None = "http://127.0.0.1:11434"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1500, ge=128, le=32000)
    request_timeout_seconds: int = Field(default=180, ge=5, le=600)


class ScheduleConfig(BaseModel):
    autopilot: bool = False
    hourly_iterations: int = Field(default=1, ge=1, le=12)
    rate_limit_per_day: int = Field(default=8, ge=1, le=500)
    quiet_hours: str = "02:00-04:00"
    scopes: list[Scope] = Field(
        default_factory=lambda: [Scope.YEARLY, Scope.WEEKLY, Scope.DAILY]
    )
    run_on_startup: bool = False

    @field_validator("scopes", mode="before")
    @classmethod
    def _normalize_scopes(cls, value: Any) -> list[str] | Any:
        if value in (None, ""):
            return [Scope.YEARLY.value, Scope.WEEKLY.value, Scope.DAILY.value]
        return value

    @property
    def interval_seconds(self) -> int:
        return max(300, round(3600 / self.hourly_iterations))


class RuntimeConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8432, ge=1, le=65535)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    ui_default_scope: Scope = Scope.YEARLY

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _normalize_cors(cls, value: Any) -> list[str]:
        if value in (None, "", []):
            return ["*"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value)


class OverthinkerConfig(BaseModel):
    class StorageConfig(BaseModel):
        backend: str = "sqlite"
        postgres_host: str = "127.0.0.1"
        postgres_port: int = Field(default=5432, ge=1, le=65535)
        postgres_database: str = "astrax"
        postgres_user: str = "astrax"
        postgres_password: str = "change_me_now"
        postgres_schema: str = "dev"
        postgres_table_prefix: str = "overthinker_"

    model: ModelConfig = Field(default_factory=ModelConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


def _normalize_legacy_payload(raw: dict[str, Any]) -> dict[str, Any]:
    payload = dict(raw or {})
    schedule = dict(payload.get("schedule") or {})
    poll_minutes = schedule.pop("poll_minutes", None)
    if poll_minutes and "hourly_iterations" not in schedule:
        try:
            schedule["hourly_iterations"] = max(1, round(60 / max(5, int(poll_minutes))))
        except (TypeError, ValueError):
            schedule["hourly_iterations"] = 1
    payload["schedule"] = schedule
    payload.setdefault("runtime", {})
    return payload


def load_config() -> OverthinkerConfig:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        cfg = OverthinkerConfig()
        save_config(cfg)
        return cfg

    with CONFIG_FILE.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return OverthinkerConfig(**_normalize_legacy_payload(raw))


def save_config(cfg: OverthinkerConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(cfg.model_dump(mode="json"), handle, sort_keys=False)
