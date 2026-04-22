# Why this exists: FastAPI entrypoint. Lifespan initializes the SQLite schema
# (APScheduler etc. plug in here in later milestones).
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routes import bookings, campaigns, generate, leads, messages, reports
from app.services.scheduler import start_scheduler, stop_scheduler
from app.utils.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Only start the scheduler when we're running under uvicorn, not during
    # test imports. Tests call scheduler.tick() directly.
    import os
    if os.getenv("DISABLE_SCHEDULER") != "1":
        start_scheduler(interval_minutes=15)
    try:
        yield
    finally:
        stop_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Lead Revival", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def set_workspace(request: Request, call_next):
        # Placeholder — M7 swaps this for real auth.
        request.state.workspace_id = 1
        return await call_next(request)

    @app.get("/api/health")
    def health():
        return {"ok": True, "demo_mode": settings.demo_mode}

    app.include_router(campaigns.router)
    app.include_router(leads.router)
    app.include_router(generate.router)
    app.include_router(messages.router)
    app.include_router(bookings.router)
    app.include_router(reports.router)

    return app


app = create_app()
