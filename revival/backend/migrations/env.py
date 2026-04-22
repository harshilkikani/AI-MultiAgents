"""Alembic environment — wires the app's SQLAlchemy Base + Settings into
the migration pipeline so `alembic upgrade head` uses the same DATABASE_URL
as the running FastAPI app.

Supports both SQLite (local dev) and Postgres (prod). Use `--sqlalchemy.url`
override on the CLI when running against a one-off DB.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Make `app` importable when running `alembic upgrade head` from this dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import after sys.path tweak so `app.*` resolves.
from app.db import Base  # noqa: E402
from app.models import orm as _orm  # noqa: F401,E402  — register models
from app.utils.settings import get_settings  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Pick DB URL from env first (Fly / docker-compose), then from Settings.
db_url = os.environ.get("DATABASE_URL") or get_settings().database_url
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without a DB connection."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # SQLite needs batch mode for ALTER TABLE to work. Postgres runs
        # straight DDL.
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=is_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
