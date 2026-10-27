"""CLI: ``uv run python -m app.eval`` from ``backend/``."""

from __future__ import annotations

import asyncio
import json
import sys

from app.eval.runner import run_golden_eval


def main() -> None:
    report = asyncio.run(run_golden_eval())
    payload = report.model_dump(mode="json")
    print(json.dumps(payload, indent=2))
    if report.failed:
        print(f"{report.failed}/{report.total} cases failed.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
