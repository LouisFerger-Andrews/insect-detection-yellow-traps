#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _to_status(outcome: str) -> str:
    return "PASS" if outcome == "success" else "FAIL"


def _build_check(name: str, label: str, outcome: str, category: str) -> dict:
    status = _to_status(outcome)
    return {
        "name": name,
        "status": status,
        "returncode": 0 if status == "PASS" else 1,
        "stdout": "",
        "stderr": "",
        "label": label,
        "category": category,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Append CI/deployment snapshot for SDLC dashboard.")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--backend-tests", required=True)
    parser.add_argument("--frontend-tests", required=True)
    parser.add_argument("--backend-build", required=True)
    parser.add_argument("--frontend-build", required=True)
    args = parser.parse_args()

    history_path = Path("02_pm_analytics_dashboard/quality_history.json")
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    else:
        history = []

    checks = [
        _build_check(
            "backend_pytest",
            "Backend tests: pytest (03 application backend)",
            args.backend_tests,
            "backend_runtime",
        ),
        _build_check(
            "frontend_vitest",
            "Frontend tests: vitest (03 application frontend)",
            args.frontend_tests,
            "frontend_runtime",
        ),
        _build_check(
            "backend_container_build",
            "Backend deployment build: docker image",
            args.backend_build,
            "deployment",
        ),
        _build_check(
            "frontend_container_build",
            "Frontend deployment build: docker image",
            args.frontend_build,
            "deployment",
        ),
    ]

    total = len(checks)
    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = total - passed
    snapshot = {
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "github-actions-ci",
        "branch": args.branch,
        "commit_sha": args.sha,
        "run_id": args.run_id,
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": failed,
        "pass_rate_pct": round((passed / total) * 100, 1) if total else 0.0,
        "checks": checks,
        "backend_runtime_summary": {
            "passed": 1 if _to_status(args.backend_tests) == "PASS" else 0,
            "failed": 1 if _to_status(args.backend_tests) == "FAIL" else 0,
            "total": 1,
        },
        "frontend_runtime_summary": {
            "passed": 1 if _to_status(args.frontend_tests) == "PASS" else 0,
            "failed": 1 if _to_status(args.frontend_tests) == "FAIL" else 0,
            "total": 1,
        },
        "runtime_tests_summary": {
            "passed_tests": 1 if _to_status(args.backend_tests) == "PASS" else 0,
            "failed_tests": 0 if _to_status(args.backend_tests) == "PASS" else 1,
            "total_tests": 1,
        },
        "runtime_tests_pass_rate_pct": 100.0 if _to_status(args.backend_tests) == "PASS" else 0.0,
        "deployment_summary": {
            "passed": sum(
                1
                for o in [args.backend_build, args.frontend_build]
                if _to_status(o) == "PASS"
            ),
            "failed": sum(
                1
                for o in [args.backend_build, args.frontend_build]
                if _to_status(o) == "FAIL"
            ),
            "total": 2,
        },
    }

    history.append(snapshot)
    history = history[-300:]
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
