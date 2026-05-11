from __future__ import annotations

from pathlib import Path

from cvcore.utils.config import load_yaml


def test_load_yaml_returns_dict(tmp_path: Path) -> None:
    p = tmp_path / "cfg.yaml"
    p.write_text("a: 1\nb:\n  c: 2\n", encoding="utf-8")
    data = load_yaml(p)
    assert data["a"] == 1
    assert data["b"]["c"] == 2

