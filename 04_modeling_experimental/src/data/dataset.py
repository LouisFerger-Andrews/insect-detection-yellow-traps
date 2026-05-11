"""Dataset interface for exports."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from data.exporters import export_to_coco, export_to_yolo
from data.loaders import ensure_raw_images


@dataclass
class Dataset:
    project: str
    raw_images_dir: Path
    processed_dir: Path
    image_glob: str = "*.jpg"
    class_names: Optional[List[str]] = None

    def _classes(self) -> List[str]:
        return self.class_names or ["insect"]

    def export_coco(self) -> Path:
        images = ensure_raw_images(self.raw_images_dir, self.image_glob)
        return export_to_coco(images, self.processed_dir / "coco", self._classes())

    def export_yolo(self) -> Path:
        images = ensure_raw_images(self.raw_images_dir, self.image_glob)
        return export_to_yolo(images, self.processed_dir / "yolo", self._classes())
