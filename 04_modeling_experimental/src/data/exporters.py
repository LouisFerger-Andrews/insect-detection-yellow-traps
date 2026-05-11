"""Dataset export utilities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List


def export_to_coco(
    images: List[Path],
    output_dir: Path,
    class_names: List[str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    annotations_path = output_dir / "annotations.json"
    payload = {
        "images": [
            {"id": idx, "file_name": img.name, "width": 0, "height": 0}
            for idx, img in enumerate(images)
        ],
        "annotations": [],
        "categories": [
            {"id": idx, "name": name} for idx, name in enumerate(class_names)
        ],
    }
    annotations_path.write_text(json.dumps(payload, indent=2))
    return annotations_path


def export_to_yolo(
    images: List[Path],
    output_dir: Path,
    class_names: List[str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    labels_dir = output_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    data_yaml = output_dir / "data.yaml"
    yaml_lines = [
        f"path: {output_dir.as_posix()}",
        "train: images",
        "val: images",
        f"names: {class_names}",
    ]
    data_yaml.write_text("\n".join(yaml_lines))
    for img in images:
        (labels_dir / f"{img.stem}.txt").write_text("")
    return data_yaml
