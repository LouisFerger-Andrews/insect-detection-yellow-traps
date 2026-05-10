from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = REPO_ROOT / "02_pm_analytics_dashboard" / "quality_history.json"


def run_check(cmd: list[str], cwd: Path) -> dict:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=1200,
        check=False,
    )
    return {
        "name": " ".join(cmd),
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "returncode": result.returncode,
        "stdout": (result.stdout or "")[-2000:],
        "stderr": (result.stderr or "")[-2000:],
    }


def parse_pytest_counts(stdout: str, stderr: str) -> dict:
    text = f"{stdout}\n{stderr}"
    passed = int(match.group(1)) if (match := re.search(r"(\d+)\s+passed", text)) else 0
    failed = int(match.group(1)) if (match := re.search(r"(\d+)\s+failed", text)) else 0
    errors = int(match.group(1)) if (match := re.search(r"(\d+)\s+error", text)) else 0
    return {"passed_tests": passed, "failed_tests": failed + errors}


def parse_vitest_counts(stdout: str, stderr: str) -> dict:
    text = f"{stdout}\n{stderr}"
    tests_line = re.search(r"Tests\s+(\d+)\s+passed(?:\s+\|\s+(\d+)\s+failed)?", text)
    if tests_line:
        passed = int(tests_line.group(1))
        failed = int(tests_line.group(2) or 0)
        return {"passed_tests": passed, "failed_tests": failed}

    passed = int(match.group(1)) if (match := re.search(r"(\d+)\s+passed", text)) else 0
    failed = int(match.group(1)) if (match := re.search(r"(\d+)\s+failed", text)) else 0
    return {"passed_tests": passed, "failed_tests": failed}


def parse_backend_coverage(path: Path) -> dict:
    if not path.exists():
        return {"coverage_pct": 0.0, "covered_lines": 0, "total_lines": 0}
    payload = json.loads(path.read_text(encoding="utf-8"))
    totals = payload.get("totals", {}) if isinstance(payload, dict) else {}
    total_lines = int(totals.get("num_statements", 0) or 0)
    covered_lines = int(totals.get("covered_lines", 0) or 0)
    pct = (covered_lines / total_lines * 100.0) if total_lines else 0.0
    return {"coverage_pct": pct, "covered_lines": covered_lines, "total_lines": total_lines}


def parse_frontend_coverage(path: Path) -> dict:
    if not path.exists():
        return {"coverage_pct": 0.0, "covered_lines": 0, "total_lines": 0}
    payload = json.loads(path.read_text(encoding="utf-8"))
    total = payload.get("total", {}) if isinstance(payload, dict) else {}
    lines = total.get("lines", {}) if isinstance(total, dict) else {}
    return {
        "coverage_pct": float(lines.get("pct", 0.0) or 0.0),
        "covered_lines": int(lines.get("covered", 0) or 0),
        "total_lines": int(lines.get("total", 0) or 0),
    }


def backend_snapshot() -> dict:
    coverage_path = REPO_ROOT / "03_application" / "backend" / ".coverage_backend.json"
    result = run_check(
        [
            "python",
            "-m",
            "pytest",
            "-q",
            "03_application/tests/backend",
            "--cov=03_application/backend/app",
            "--cov-report=term",
            f"--cov-report=json:{coverage_path}",
        ],
        REPO_ROOT,
    )
    result["label"] = "Backend tests: pytest (03 application backend)"
    result["category"] = "backend_runtime"
    result.update(parse_pytest_counts(result.get("stdout", ""), result.get("stderr", "")))
    result.update(parse_backend_coverage(coverage_path))
    return result


def frontend_snapshot() -> dict:
    frontend_dir = REPO_ROOT / "03_application" / "frontend"
    coverage_path = frontend_dir / "coverage" / "coverage-summary.json"
    result = run_check(["npm", "run", "test", "--", "--coverage"], frontend_dir)
    result["label"] = "Frontend tests: vitest (03 application frontend)"
    result["category"] = "frontend_runtime"
    result.update(parse_vitest_counts(result.get("stdout", ""), result.get("stderr", "")))
    result.update(parse_frontend_coverage(coverage_path))
    return result


def build_snapshot(checks: list[dict]) -> dict:
    passed_checks = sum(1 for item in checks if item.get("status") == "PASS")
    failed_checks = sum(1 for item in checks if item.get("status") == "FAIL")
    passed_tests = sum(int(item.get("passed_tests", 0) or 0) for item in checks)
    failed_tests = sum(int(item.get("failed_tests", 0) or 0) for item in checks)
    total_tests = passed_tests + failed_tests
    covered_lines = sum(int(item.get("covered_lines", 0) or 0) for item in checks)
    total_lines = sum(int(item.get("total_lines", 0) or 0) for item in checks)

    backend = next((item for item in checks if item.get("category") == "backend_runtime"), {})
    frontend = next((item for item in checks if item.get("category") == "frontend_runtime"), {})
    return {
        "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "total_checks": len(checks),
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "pass_rate_pct": round((passed_checks / len(checks)) * 100, 1) if checks else 0.0,
        "checks": checks,
        "backend_runtime_summary": {"passed": 1 if backend.get("status") == "PASS" else 0, "failed": 1 if backend.get("status") == "FAIL" else 0, "total": 1},
        "backend_runtime_pass_rate_pct": 100.0 if backend.get("status") == "PASS" else 0.0,
        "frontend_runtime_summary": {"passed": 1 if frontend.get("status") == "PASS" else 0, "failed": 1 if frontend.get("status") == "FAIL" else 0, "total": 1},
        "frontend_runtime_pass_rate_pct": 100.0 if frontend.get("status") == "PASS" else 0.0,
        "runtime_tests_summary": {
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "total_tests": total_tests,
        },
        "runtime_tests_pass_rate_pct": round((passed_tests / total_tests) * 100, 1) if total_tests else 0.0,
        "backend_coverage_pct": float(backend.get("coverage_pct", 0.0) or 0.0),
        "frontend_coverage_pct": float(frontend.get("coverage_pct", 0.0) or 0.0),
        "application_coverage_pct": round((covered_lines / total_lines) * 100, 1) if total_lines else 0.0,
        "coverage_pct": round((covered_lines / total_lines) * 100, 1) if total_lines else 0.0,
    }


def main() -> int:
    history = []
    if HISTORY_PATH.exists():
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            history = []

    checks = [backend_snapshot(), frontend_snapshot()]
    snapshot = build_snapshot(checks)
    history.append(snapshot)
    HISTORY_PATH.write_text(json.dumps(history[-12:], indent=2) + "\n", encoding="utf-8")

    return 0 if all(item.get("status") == "PASS" for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
