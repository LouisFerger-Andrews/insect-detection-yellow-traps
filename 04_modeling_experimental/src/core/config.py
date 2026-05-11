"""Configuration loading and validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class CommonConfig:
    project: str
    raw_dir: Path
    processed_dir: Path
    image_glob: str


def _resolve_path(value: str, project: str) -> Path:
    expanded = value.format(project=project)
    return Path(expanded)


def load_config(path: Path, project: str) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    data.setdefault("project", project)
    return data


def parse_common_config(cfg: Dict[str, Any]) -> CommonConfig:
    project = cfg.get("project", "default")
    data_cfg = cfg.get("data", {})
    raw_dir = _resolve_path(
        data_cfg.get("raw_dir", "04_modeling_experimental/data/raw/{project}"),
        project,
    )
    processed_dir = _resolve_path(
        data_cfg.get("processed_dir", "04_modeling_experimental/data/processed/{project}"),
        project,
    )
    image_glob = data_cfg.get("image_glob", "*.jpg")
    return CommonConfig(
        project=project,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        image_glob=image_glob,
    )
