"""M13 tests: auth middleware. Prod mode requires a Bearer JWT; DEMO auto-
logs-in; cross-workspace access blocked even with a valid JWT."""
from __future__ import annotations

import os
import time

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

JWT_SECRET = "unit-test-secret"


def _make_token(sub: str, email: str = "x@y.com") -> str:
    return pyjwt.encode(
        {"sub": sub, "email": email, "exp": int(time.time()) + 3600},
        JWT_SECRET, algorithm="HS256",
    )


@pytest.fixture
def prod_app(tmp_path, monkeypatch):
    """App with DEMO_MODE=false and a real JWT secret, so auth enforces."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.delenv("REVIVAL_TEST_BYPASS", raising=False)

    import sys
    for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        sys.modules.pop(mod, None)

    from app.db import SessionLocal, init_db
    from app.main import app as fresh_app
    init_db()
    return fresh_app, SessionLocal


@pytest.mark.asyncio
async def test_prod_mode_rejects_unauthenticated_api_calls(prod_app):
    app, _ = prod_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/campaigns")
        assert r.status_code == 401
        assert "authenticated" in r.json()["detail"]


@pytest.mark.asyncio
async def test_prod_mode_rejects_garbage_token(prod_app):
    app, _ = prod_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/campaigns", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_prod_mode_accepts_valid_jwt_with_membership(prod_app):
    app, SessionLocal = prod_app
    # Pre-seed user + workspace + membership.
    from app.models.orm import User, Workspace, WorkspaceMember
    db = SessionLocal()
    try:
        user = User(external_id="user-abc-123", email="alice@example.com")
        ws = Workspace(id=7, name="Alice's Shop")
        db.add_all([user, ws])
        db.commit()
        db.refresh(user)
        db.add(WorkspaceMember(user_id=user.id, workspace_id=7, role="owner"))
        db.commit()
    finally:
        db.close()

    token = _make_token("user-abc-123", "alice@example.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["email"] == "alice@example.com"
        assert body["workspace_id"] == 7


@pytest.mark.asyncio
async def test_prod_mode_denies_non_member_workspace(prod_app):
    app, SessionLocal = prod_app
    from app.models.orm import User, Workspace, WorkspaceMember
    db = SessionLocal()
    try:
        user = User(external_id="user-xyz-987", email="bob@example.com")
        ws1 = Workspace(id=10, name="Bob Shop")
        ws2 = Workspace(id=11, name="Not Bob")
        db.add_all([user, ws1, ws2])
        db.commit()
        db.refresh(user)
        # Bob belongs to ws 10, NOT ws 11.
        db.add(WorkspaceMember(user_id=user.id, workspace_id=10))
        db.commit()
    finally:
        db.close()

    token = _make_token("user-xyz-987", "bob@example.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Asking for ws 11 via header → 401 (no membership).
        r = await c.get(
            "/api/campaigns",
            headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": "11"},
        )
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_demo_mode_login_returns_stub_token(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")

    import sys
    for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        sys.modules.pop(mod, None)

    from app.db import init_db
    from app.main import app as fresh_app
    init_db()

    async with AsyncClient(transport=ASGITransport(app=fresh_app), base_url="http://t") as c:
        r = await c.post("/api/auth/login", json={"email": "anyone@ex.com"})
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "demo"
        assert body["token"].startswith("demo-")


@pytest.mark.asyncio
async def test_webhooks_remain_public(prod_app):
    app, _ = prod_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Health check — still open.
        r = await c.get("/api/health")
        assert r.status_code == 200
        # Demo info — still open (returns 'seeded: false').
        r = await c.get("/api/demo/info")
        assert r.status_code == 200
        # Twilio webhook — auth middleware skips it; sig verification will fail
        # (no signature), which is the expected 403, not 401.
        r = await c.post(
            "/webhooks/twilio/inbound",
            data={"From": "+1", "Body": "hi"},
        )
        assert r.status_code == 403  # signature, not auth
