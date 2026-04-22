# Why this exists: CLI entrypoint for rebuilding the demo workspace.
# Usage: python -m scripts.seed_demo   (from revival/backend/)
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `app` importable when running as a script from revival/backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DISABLE_SCHEDULER", "1")


def main() -> int:
    from app.db import SessionLocal, init_db
    init_db()

    from app.services.demo_seed import build_demo
    db = SessionLocal()
    try:
        summary = build_demo(db)
    finally:
        db.close()

    print("demo seeded:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
