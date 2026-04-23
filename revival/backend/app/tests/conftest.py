from __future__ import annotations

import os

import pytest

# Force DEMO_MODE + an in-memory-friendly SQLite URL before any app import
# picks up the real .env.
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./_revival_test.db")
# Allow webhook signature bypass for the automated test suite.
os.environ.setdefault("REVIVAL_TEST_BYPASS", "1")


@pytest.fixture(autouse=True)
def _reset_module_state():
    """The DNC deny list is cached at module scope — invalidate before every
    test so fixture data from another test doesn't leak into the next one.
    Same for scheduler heartbeat (otherwise /api/health flaps between tests)."""
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
