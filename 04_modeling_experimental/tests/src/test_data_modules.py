from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from data.coco import (
    CocoSplitConfig,
    _bbox_to_yolo,
    _clip_box,
    build_category_index,
    convert_coco_split_to_yolo,
    group_annotations,
    load_coco,
    write_yolo_dataset_yaml,
)
from data.dataset import Dataset
from data.exporters import export_to_coco, export_to_yolo
from data.loaders import ensure_raw_images, list_images
from data.masking import MaskConfig, apply_yellow_mask
from eval.metrics import counting_error, mean_average_precision, summarize_metrics


def test_load_coco_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_coco(tmp_path / "missing.json")


def test_build_category_index_deduplicates_names_case_insensitive() -> None:
    coco = {
        "categories": [
            {"id": 2, "name": "Insects"},
            {"id": 1, "name": "insects"},
            {"id": 3, "name": "   "},
            {"id": 4, "name": "Fly"},
        ]
    }
    id_to_idx, names = build_category_index(coco)
    assert names == ["insects", "Fly"]
    assert id_to_idx == {1: 0, 2: 0, 4: 1}


def test_group_annotations_and_bbox_helpers() -> None:
    grouped = group_annotations(
        {"annotations": [{"image_id": 10}, {"image_id": 10}, {"image_id": 11}]}
    )
    assert len(grouped[10]) == 2
    assert len(grouped[11]) == 1

    x, y, w, h = _clip_box(-5, -4, 20, 10, 10, 10)
    assert (x, y, w, h) == (0.0, 0.0, 10.0, 6.0)

    cx, cy, nw, nh = _bbox_to_yolo(0.0, 0.0, 10.0, 10.0, 20, 20)
    assert (cx, cy, nw, nh) == (0.25, 0.25, 0.5, 0.5)


def test_convert_coco_split_to_yolo_and_yaml(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    cv2.imwrite(str(images_dir / "sample.jpg"), image)

    coco_path = tmp_path / "annotations.json"
    coco_path.write_text(
        json.dumps(
            {
                "images": [{"id": 1, "file_name": "sample.jpg"}],
                "annotations": [
                    {"image_id": 1, "category_id": 1, "bbox": [10, 10, 20, 20]},
                    {"image_id": 1, "category_id": 99, "bbox": [10, 10, 20, 20]},
                    {"image_id": 1, "category_id": 1, "bbox": [0, 0, 1, 1]},
                ],
                "categories": [{"id": 1, "name": "insect"}],
            }
        ),
        encoding="utf-8",
    )

    split = CocoSplitConfig(
        name="train",
        images_dir=images_dir,
        annotations_path=coco_path,
    )
    out_dir = tmp_path / "yolo"
    names = convert_coco_split_to_yolo(
        split=split,
        output_dir=out_dir,
        mask_cfg=MaskConfig(enabled=False),
    )
    assert names == ["insect"]
    assert (out_dir / "images" / "train" / "sample.jpg").exists()
    label_path = out_dir / "labels" / "train" / "sample.txt"
    assert label_path.exists()
    label_lines = label_path.read_text(encoding="utf-8").splitlines()
    assert len(label_lines) == 1
    assert label_lines[0].startswith("0 ")

    data_yaml = write_yolo_dataset_yaml(
        output_dir=out_dir,
        class_names=names,
        train="images/train",
        val="images/val",
        test="images/test",
    )
    content = data_yaml.read_text(encoding="utf-8")
    assert "train: images/train" in content
    assert "test: images/test" in content
    assert "0: insect" in content


def test_apply_yellow_mask_disabled_and_crop_mode() -> None:
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    # Bright yellow in BGR
    img[20:80, 30:90] = (0, 255, 255)

    unchanged, crop = apply_yellow_mask(img, MaskConfig(enabled=False))
    assert crop is None
    assert unchanged.shape == img.shape

    cropped, crop_rect = apply_yellow_mask(
        img,
        MaskConfig(enabled=True, mode="crop", min_area_ratio=0.01),
    )
    assert crop_rect is not None
    assert cropped.size > 0


def test_list_images_and_ensure_raw_images(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    assert list_images(raw, "*.jpg") == []
    with pytest.raises(FileNotFoundError):
        ensure_raw_images(raw, "*.jpg")

    raw.mkdir()
    (raw / "a.jpg").write_bytes(b"x")
    (raw / "b.jpg").write_bytes(b"x")
    images = ensure_raw_images(raw, "*.jpg")
    assert [p.name for p in images] == ["a.jpg", "b.jpg"]


def test_exporters_and_dataset_exports(tmp_path: Path) -> None:
    images = [tmp_path / "i1.jpg", tmp_path / "i2.jpg"]
    for image in images:
        image.write_bytes(b"x")

    coco_out = export_to_coco(images, tmp_path / "out_coco", ["insect"])
    payload = json.loads(coco_out.read_text(encoding="utf-8"))
    assert len(payload["images"]) == 2
    assert payload["categories"][0]["name"] == "insect"

    yolo_out = export_to_yolo(images, tmp_path / "out_yolo", ["insect"])
    assert yolo_out.exists()
    assert (tmp_path / "out_yolo" / "labels" / "i1.txt").exists()
    assert (tmp_path / "out_yolo" / "labels" / "i2.txt").exists()

    ds = Dataset(
        project="demo",
        raw_images_dir=tmp_path,
        processed_dir=tmp_path / "processed",
        image_glob="*.jpg",
    )
    assert ds._classes() == ["insect"]
    assert ds.export_coco().exists()
    assert ds.export_yolo().exists()


def test_eval_metrics_helpers() -> None:
    assert mean_average_precision([], []) == 0.0
    assert counting_error([1, 2, 3], [1]) == 2
    summary = summarize_metrics([1], [1, 2])
    assert summary["mAP"] == 0.0
    assert summary["count_error"] == 1
