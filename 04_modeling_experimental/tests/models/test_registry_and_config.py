from __future__ import annotations

from pathlib import Path

import pytest

from core.config import load_config, parse_common_config
from core.registry import get_approach, list_approaches


def test_list_and_get_approaches() -> None:
    names = list_approaches()
    assert {"yolo", "rtdetr", "classical_cv"}.issubset(set(names.keys()))
    cls = get_approach("yolo")
    assert cls.__name__.lower().startswith("yolo")


def test_get_unknown_approach_raises() -> None:
    with pytest.raises(KeyError):
        get_approach("unknown_approach")


def test_load_and_parse_common_config(tmp_path: Path) -> None:
    cfg_path = tmp_path / "base.yaml"
    cfg_path.write_text(
        """
project: insects
data:
  raw_dir: 04_modeling_experimental/data/raw/{project}
  processed_dir: data/processed/{project}
  image_glob: "*.png"
        """.strip(),
        encoding="utf-8",
    )
    cfg = load_config(cfg_path, project="insects")
    common = parse_common_config(cfg)
    assert common.project == "insects"
    assert str(common.raw_dir).endswith("04_modeling_experimental/data/raw/insects")
    assert str(common.processed_dir).endswith("data/processed/insects")
    assert common.image_glob == "*.png"
