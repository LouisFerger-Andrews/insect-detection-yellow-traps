"""RT-DETR style transformer detector stub."""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, List

from core.approach_base import BaseApproach
from core.config import parse_common_config
from data.dataset import Dataset
from utils.logging import get_logger


class RTDETRApproach(BaseApproach):
    """Transformer detector approach (RT-DETR style)."""

    def prepare_data(self) -> None:
        common = parse_common_config(self.ctx.config)
        dataset = Dataset(
            project=common.project,
            raw_images_dir=common.raw_dir / "images",
            processed_dir=common.processed_dir,
            image_glob=common.image_glob,
            class_names=["insect"],
        )
        coco_path = dataset.export_coco()
        logger = get_logger("rtdetr", self.ctx.run_dir)
        logger.info("Exported COCO dataset to %s", coco_path.parent)

    def train(self) -> None:
        logger = get_logger("rtdetr", self.ctx.run_dir)
        try:
            importlib.import_module("torch")
        except ImportError as exc:
            raise RuntimeError("PyTorch not installed. Install with: pip install torch") from exc
        logger.info("Training stub - TODO: integrate RT-DETR training.")

    def evaluate(self) -> Dict[str, float]:
        logger = get_logger("rtdetr", self.ctx.run_dir)
        logger.info("Evaluation stub - returning placeholder metrics.")
        return {"mAP": 0.0, "count_error": 0.0}

    def predict(self, image_path: Path) -> List[Dict[str, Any]]:
        logger = get_logger("rtdetr", self.ctx.run_dir)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        try:
            from PIL import Image

            Image.open(image_path).convert("RGB")
        except ImportError as exc:
            raise RuntimeError("Pillow not installed. Install with: pip install pillow") from exc
        logger.info("Predict stub - returning empty detections.")
        return []

    def export(self) -> Path:
        export_dir = self.ctx.run_dir / "export"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "README.txt").write_text("TODO: export RT-DETR model")
        return export_dir
