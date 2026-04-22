# Why this exists: FastAPI entrypoint. Lifespan initializes the SQLite schema
# (APScheduler etc. plug in here in later milestones).
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.db import SessionLocal, init_db
from app.routes import auth, billing, bookings, campaigns, compliance, demo, generate, leads, messages, reports
from app.services.auth import resolve_auth_context
from app.services.scheduler import start_scheduler, stop_scheduler
from app.utils.settings import get_settings

# Paths that skip JWT auth — webhooks verify their own signatures, the demo
# checkout page is HTML, and health is public.
_PUBLIC_PATH_PREFIXES = (
    "/api/health",
    "/api/auth/",
    "/api/demo/",
    "/webhooks/",
    "/demo/checkout",
    "/docs",
    "/openapi.json",
    "/redoc",
)


def _is_public_path(path: str) -> bool:
    return any(path.startswith(p) for p in _PUBLIC_PATH_PREFIXES)


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
    async def resolve_auth(request: Request, call_next):
        """M13 — auth resolution. In prod, /api/* requires a valid Bearer
        JWT; DEMO_MODE auto-logs in a demo user; webhooks + demo endpoints
        are public. Workspace id comes from membership (verified), not a
        spoofable header."""
        path = request.url.path

        # Public routes don't need auth; they still get a default workspace
        # so legacy handlers that read request.state.workspace_id keep
        # working (webhook/demo/auth handlers don't all need it).
        if _is_public_path(path):
            # Parse the query/header for webhook-test helpers.
            ws_q = request.query_params.get("workspace")
            try:
                request.state.workspace_id = int(ws_q) if ws_q else 1
            except ValueError:
                request.state.workspace_id = 1
            request.state.user_id = None
            request.state.is_demo = True
            return await call_next(request)

        # Authed routes.
        authorization = request.headers.get("Authorization")
        ws_hdr = request.headers.get("X-Workspace-Id")
        ws_qp = request.query_params.get("workspace")
        try:
            requested_ws = int(ws_hdr or ws_qp) if (ws_hdr or ws_qp) else None
        except ValueError:
            requested_ws = None

        db = SessionLocal()
        try:
            ctx = resolve_auth_context(
                db,
                authorization_header=authorization,
                requested_workspace=requested_ws,
            )
        finally:
            db.close()

        if ctx is None:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "not authenticated"}, status_code=401)

        request.state.user_id = ctx.user_id
        request.state.external_id = ctx.external_id
        request.state.workspace_id = ctx.workspace_id
        request.state.is_demo = ctx.is_demo
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
    app.include_router(billing.router)
    app.include_router(demo.router)
    app.include_router(compliance.router)
    app.include_router(auth.router)

    return app


app = create_app()
