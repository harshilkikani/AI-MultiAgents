from __future__ import annotations

import os

import pytest

# Force DEMO_MODE + an in-memory-friendly SQLite URL before any app import
# picks up the real .env.
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./_revival_test.db")
# Allow webhook signature bypass for the automated test suite.
os.environ.setdefault("REVIVAL_TEST_BYPASS", "1")


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Fresh FastAPI app backed by a scratch SQLite DB.

    Purges every `app.*` module so the new DATABASE_URL is picked up
    cleanly. Used by every test that hits the HTTP layer. Tests with
    special env requirements (e.g. signature verification, health 503)
    override by defining a local `app` fixture that shadows this one.
    """
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")

    import sys
    for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        sys.modules.pop(mod, None)

    from app.db import init_db
    from app.main import app as fresh_app
    init_db()
    return fresh_app


@pytest.fixture(autouse=True)
def _reset_module_state():
    """The DNC deny list is cached at module scope — invalidate before every
    test so fixture data from another test doesn't leak into the next one.
    Same for the scheduler heartbeat (otherwise /api/health flaps)."""
    try:
        from app.services import compliance as _comp
        _comp.invalidate_dnc_cache()
    except Exception:
        pass
    try:
        from app.services import scheduler as _sched
        _sched._last_tick_at = None
        _sched._last_tick_result = None
    except Exception:
        pass
    yield
