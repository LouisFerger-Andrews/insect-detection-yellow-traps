"""COCO loading and conversion utilities."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2

from data.masking import MaskConfig, apply_yellow_mask


@dataclass
class CocoSplitConfig:
    name: str
    images_dir: Path
    annotations_path: Path


def load_coco(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"COCO annotations not found: {path}")
    return json.loads(path.read_text())


def build_category_index(coco: Dict) -> Tuple[Dict[int, int], List[str]]:
    """Build category id->index map and de-duplicate same-name categories.

    Some exported datasets can contain repeated categories with different IDs
    but identical class names (e.g. ["Insects", "Insects"]). YOLO should see
    one class index per semantic class name, so we merge by normalized name.
    """
    categories = sorted(coco.get("categories", []), key=lambda c: c["id"])
    id_to_index: Dict[int, int] = {}
    names: List[str] = []
    name_to_index: Dict[str, int] = {}

    for cat in categories:
        raw_name = str(cat.get("name", "")).strip()
        if not raw_name:
            continue
        norm = raw_name.casefold()
        if norm not in name_to_index:
            name_to_index[norm] = len(names)
            names.append(raw_name)
        id_to_index[int(cat["id"])] = name_to_index[norm]

    return id_to_index, names


def group_annotations(coco: Dict) -> Dict[int, List[Dict]]:
    grouped: Dict[int, List[Dict]] = {}
    for ann in coco.get("annotations", []):
        grouped.setdefault(ann["image_id"], []).append(ann)
    return grouped


def _clip_box(
    x: float, y: float, w: float, h: float, max_w: int, max_h: int
) -> Tuple[float, float, float, float]:
    x1 = max(0.0, x)
    y1 = max(0.0, y)
    x2 = min(float(max_w), x + w)
    y2 = min(float(max_h), y + h)
    new_w = max(0.0, x2 - x1)
    new_h = max(0.0, y2 - y1)
    return x1, y1, new_w, new_h


def _bbox_to_yolo(
    x: float, y: float, w: float, h: float, img_w: int, img_h: int
) -> Tuple[float, float, float, float]:
    cx = (x + w / 2.0) / float(img_w)
    cy = (y + h / 2.0) / float(img_h)
    return cx, cy, w / float(img_w), h / float(img_h)


def convert_coco_split_to_yolo(
    split: CocoSplitConfig,
    output_dir: Path,
    mask_cfg: MaskConfig,
) -> List[str]:
    coco = load_coco(split.annotations_path)
    id_to_index, names = build_category_index(coco)
    anns_by_image = group_annotations(coco)

    images_out = output_dir / "images" / split.name
    labels_out = output_dir / "labels" / split.name
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    for image in coco.get("images", []):
        file_name = image["file_name"]
        image_path = split.images_dir / file_name
        if not image_path.exists():
            continue

        img = cv2.imread(str(image_path))
        if img is None:
            continue

        img_h, img_w = img.shape[:2]
        out_img = img
        crop = None
        if mask_cfg.enabled:
            out_img, crop = apply_yellow_mask(img, mask_cfg)

        out_h, out_w = out_img.shape[:2]
        out_name = Path(file_name).name
        cv2.imwrite(str(images_out / out_name), out_img)

        label_lines: List[str] = []
        for ann in anns_by_image.get(image["id"], []):
            cat_id = ann["category_id"]
            if cat_id not in id_to_index:
                continue
            x, y, w, h = ann["bbox"]
            if crop is not None:
                x, y, w, h = _clip_box(
                    x - crop[0], y - crop[1], w, h, out_w, out_h
                )
            x, y, w, h = _clip_box(x, y, w, h, out_w, out_h)
            if w <= 1.0 or h <= 1.0:
                continue
            cx, cy, nw, nh = _bbox_to_yolo(x, y, w, h, out_w, out_h)
            label_lines.append(
                f"{id_to_index[cat_id]} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"
            )

        (labels_out / f"{Path(out_name).stem}.txt").write_text(
            "\n".join(label_lines)
        )

    return names


def write_yolo_dataset_yaml(
    output_dir: Path, class_names: List[str], train: str, val: str, test: Optional[str]
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    data_yaml = output_dir / "data.yaml"
    lines = [
        f"path: {output_dir.as_posix()}",
        f"train: {train}",
        f"val: {val}",
    ]
    if test:
        lines.append(f"test: {test}")
    names_map = {idx: name for idx, name in enumerate(class_names)}
    lines.append("names:")
    lines.extend([f"  {idx}: {name}" for idx, name in names_map.items()])
    data_yaml.write_text("\n".join(lines))
    return data_yaml
