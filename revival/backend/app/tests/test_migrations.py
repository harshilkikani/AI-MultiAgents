"""M14 tests: Alembic baseline migration applies cleanly on a fresh DB
and produces the same schema shape `init_db()` produces, so ops can pick
either path without drift."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _table_names(url: str) -> set[str]:
    from sqlalchemy import create_engine, inspect
    eng = create_engine(url)
    try:
        return set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


def test_alembic_upgrade_head_creates_all_tables(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'alembic_test.db'}"
    backend_dir = Path(__file__).resolve().parents[2]

    monkeypatch.setenv("DATABASE_URL", url)
    # Run alembic as a subprocess so we don't pollute the in-process
    # SQLAlchemy engine used by other tests.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env={**__import__("os").environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic failed: {result.stderr}"

    tables = _table_names(url)
    expected = {
        "alembic_version",
        "workspaces", "users", "workspace_members",
        "campaigns", "leads", "messages",
        "opt_outs", "compliance_events",
    }
    assert expected.issubset(tables), f"missing tables: {expected - tables}"


def test_init_db_and_alembic_agree_on_schema(tmp_path, monkeypatch):
    """The set of tables created by init_db() should match the set created
    by alembic upgrade head, minus Alembic's bookkeeping table. Prevents
    drift where a model is added without a migration, or vice versa."""
    # init_db path
    init_url = f"sqlite:///{tmp_path / 'init.db'}"
    monkeypatch.setenv("DATABASE_URL", init_url)

    import sys as _sys
    for mod in [m for m in list(_sys.modules) if m == "app" or m.startswith("app.")]:
        _sys.modules.pop(mod, None)
    from app.db import init_db
    init_db()
    init_tables = _table_names(init_url) - {"alembic_version"}

    # alembic path
    alembic_url = f"sqlite:///{tmp_path / 'alembic.db'}"
    backend_dir = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env={**__import__("os").environ, "DATABASE_URL": alembic_url},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"alembic failed: {result.stderr}"
    alembic_tables = _table_names(alembic_url) - {"alembic_version"}

    assert init_tables == alembic_tables, (
        f"schema drift!\n"
        f"  only in init_db: {init_tables - alembic_tables}\n"
        f"  only in alembic: {alembic_tables - init_tables}"
    )
