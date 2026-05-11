from __future__ import annotations

from pathlib import Path
import sys

from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from cli import app  # noqa: E402


runner = CliRunner()


def test_list_approaches() -> None:
    result = runner.invoke(app, ["list-approaches"])
    assert result.exit_code == 0
    assert "yolo" in result.stdout
    assert "rtdetr" in result.stdout
    assert "classical_cv" in result.stdout
