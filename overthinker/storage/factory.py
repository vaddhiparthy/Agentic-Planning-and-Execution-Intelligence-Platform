from __future__ import annotations

from overthinker.core.config import OverthinkerConfig, load_config
from overthinker.storage.postgres_repository import PostgresRepository
from overthinker.storage.repository import SQLiteRepository


def create_repository(cfg: OverthinkerConfig | None = None):
    cfg = cfg or load_config()
    if cfg.storage.backend.lower() == "postgres":
        return PostgresRepository(cfg.storage)
    return SQLiteRepository()
