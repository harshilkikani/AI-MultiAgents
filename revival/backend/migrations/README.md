# Alembic migrations

```bash
# From revival/backend/
source .venv/Scripts/activate   # or bin/activate on macOS/Linux

# Apply all pending migrations to the configured DATABASE_URL.
alembic upgrade head

# Autogenerate a new migration after editing models/orm.py.
alembic revision --autogenerate -m "add foo column"
# Review the generated file before committing — autogen can miss enum
# changes and needs tweaks for anything non-trivial.

# Roll back one migration.
alembic downgrade -1
```

## Why this exists

SQLite + `Base.metadata.create_all()` is fine for local dev but can't
evolve a running prod database. Alembic gives us a reviewed audit trail
of every schema change so customer data isn't wiped when we add a column.

## Baseline

`0001_baseline.py` captures the schema as of M13 (workspaces, users,
workspace_members, campaigns, leads, messages, opt_outs,
compliance_events). Every future schema change gets a new revision file.

## Production deploy

The Fly.io `release_command` runs `alembic upgrade head` before the new
revision goes live. Local dev keeps using `init_db()` (create_all) for
speed; if you prefer migrations locally too, just run
`alembic upgrade head` before your first `uvicorn` start.
