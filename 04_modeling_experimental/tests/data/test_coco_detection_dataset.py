from __future__ import annotations

import json
from pathlib import Path

import pytest

from cvcore.data.datasets import COCODetectionDataset


def _write_coco_file(path: Path) -> None:
    payload = {
        "images": [{"id": 1, "file_name": "img1.jpg", "width": 32, "height": 24}],
        "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [1, 2, 3, 4]}],
        "categories": [{"id": 1, "name": "insect"}],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_coco_dataset_metadata_and_sample_without_loading_images(tmp_path: Path) -> None:
    ann_file = tmp_path / "_annotations.coco.json"
    _write_coco_file(ann_file)
    (tmp_path / "img1.jpg").write_bytes(b"fake-jpg")

    ds = COCODetectionDataset(root=tmp_path, annotation_file=ann_file, load_images=False)
    assert len(ds) == 1
    meta = ds.get_metadata()
    assert meta["num_images"] == 1
    assert meta["num_classes"] == 1
    assert meta["class_names"] == ["insect"]

    sample = ds[0]
    assert sample["file_name"] == "img1.jpg"
    assert sample["image_id"] == 1
    assert len(sample["annotations"]) == 1
    assert isinstance(sample["image"], Path)


def test_coco_dataset_missing_annotation_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        COCODetectionDataset(root=tmp_path, annotation_file=tmp_path / "missing.json", load_images=False)

