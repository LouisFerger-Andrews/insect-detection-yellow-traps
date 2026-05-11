from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from ultralytics import YOLO

from app.core.config import get_settings

logger = logging.getLogger(__name__)
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


class InferenceService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._model: YOLO | None = None

    def _get_model(self) -> YOLO:
        if self._model is None:
            weights_path = Path(self.settings.model_weights_path).resolve()
            if not weights_path.exists():
                raise FileNotFoundError(f'Model weights not found: {weights_path}')
            self._model = YOLO(str(weights_path))
        return self._model

    def run(self, image_path: Path) -> List[Dict[str, Any]]:
        image_path = Path(image_path)
        if not image_path.exists():
            raise ValueError(f'Image not found for inference: {image_path}')
        suffix = image_path.suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            allowed = ', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))
            raise ValueError(f'Unsupported inference image type "{suffix}". Allowed: {allowed}')

        model = self._get_model()
        try:
            results = model.predict(
                source=str(image_path),
                imgsz=self.settings.model_image_size,
                conf=self.settings.model_confidence,
                verbose=False,
            )
        except Exception as exc:
            logger.exception('Inference prediction failed for image=%s', image_path)
            raise RuntimeError('Inference prediction failed') from exc

        detections: List[Dict[str, Any]] = []
        if not results:
            return detections

        for box in results[0].boxes:
            xyxy = box.xyxy[0].tolist()
            detections.append(
                {
                    'bbox_xyxy': [float(value) for value in xyxy],
                    'confidence': float(box.conf[0]),
                    'class_id': int(box.cls[0]),
                }
            )
        return detections
