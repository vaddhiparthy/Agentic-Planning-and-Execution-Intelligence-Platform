from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from overthinker.api.routes import router
from overthinker.core.config import load_config
from overthinker.core.paths import UI_DIR
from overthinker.services.scheduler import OverthinkerScheduler
from overthinker.storage.factory import create_repository


def create_app() -> FastAPI:
    cfg = load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository = create_repository(cfg)
        repository.initialize()
        scheduler = OverthinkerScheduler(repository)
        app.state.repository = repository
        app.state.scheduler = scheduler
        await scheduler.start()
        try:
            yield
        finally:
            await scheduler.shutdown()

    app = FastAPI(title="ASTRA-X Overthinker v2", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.runtime.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if UI_DIR.exists():
        app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")

    app.include_router(router)

    return app
