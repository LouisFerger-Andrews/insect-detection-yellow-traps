from __future__ import annotations

import json
from pathlib import Path

from cvcore.data.loaders import build_coco_dataset


def test_build_coco_dataset_from_relative_annotation(tmp_path: Path) -> None:
    ann = tmp_path / "_annotations.coco.json"
    payload = {
        "images": [{"id": 1, "file_name": "img.jpg"}],
        "annotations": [],
        "categories": [],
    }
    ann.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "img.jpg").write_bytes(b"x")

    ds = build_coco_dataset(root=tmp_path, annotation_file="_annotations.coco.json")
    assert len(ds) == 1
    sample = ds[0]
    assert sample["file_name"] == "img.jpg"

