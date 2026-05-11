"""Classical CV baseline using thresholding + connected components."""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, List

from core.approach_base import BaseApproach
from core.config import parse_common_config
from data.loaders import ensure_raw_images
from utils.logging import get_logger


class ClassicalCVApproach(BaseApproach):
    """OpenCV-based baseline."""

    def prepare_data(self) -> None:
        common = parse_common_config(self.ctx.config)
        images_dir = common.raw_dir / "images"
        ensure_raw_images(images_dir, common.image_glob)
        logger = get_logger("classical_cv", self.ctx.run_dir)
        logger.info("No export needed for classical CV baseline.")

    def train(self) -> None:
        logger = get_logger("classical_cv", self.ctx.run_dir)
        logger.info("Classical CV has no training step.")

    def evaluate(self) -> Dict[str, float]:
        logger = get_logger("classical_cv", self.ctx.run_dir)
        logger.info("Evaluation stub - returning placeholder metrics.")
        return {"mAP": 0.0, "count_error": 0.0}

    def predict(self, image_path: Path) -> List[Dict[str, Any]]:
        logger = get_logger("classical_cv", self.ctx.run_dir)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        try:
            cv2 = importlib.import_module("cv2")
        except ImportError as exc:
            raise RuntimeError(
                "OpenCV not installed. Install with: pip install opencv-python"
            ) from exc
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Failed to read image: {image_path}")
        logger.info("Predict stub - returning empty detections.")
        return []

    def export(self) -> Path:
        export_dir = self.ctx.run_dir / "export"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "README.txt").write_text("TODO: export classical CV artifacts")
        return export_dir
