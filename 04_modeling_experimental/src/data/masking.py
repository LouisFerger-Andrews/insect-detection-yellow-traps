"""Masking utilities for yellow sheet segmentation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class MaskConfig:
    enabled: bool = False
    mode: str = "mask"  # "mask" or "crop"
    hsv_lower: Tuple[int, int, int] = (15, 60, 60)
    hsv_upper: Tuple[int, int, int] = (40, 255, 255)
    min_area_ratio: float = 0.05


def apply_yellow_mask(
    image_bgr: np.ndarray, cfg: MaskConfig
) -> Tuple[np.ndarray, Optional[Tuple[int, int, int, int]]]:
    """Return masked image and optional crop rect (x, y, w, h)."""
    if not cfg.enabled:
        return image_bgr, None

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array(cfg.hsv_lower, dtype=np.uint8)
    upper = np.array(cfg.hsv_upper, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image_bgr, None

    h, w = image_bgr.shape[:2]
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < cfg.min_area_ratio * float(h * w):
        return image_bgr, None

    sheet_mask = np.zeros_like(mask)
    cv2.drawContours(sheet_mask, [largest], -1, 255, thickness=-1)
    masked = cv2.bitwise_and(image_bgr, image_bgr, mask=sheet_mask)

    if cfg.mode == "crop":
        x, y, cw, ch = cv2.boundingRect(largest)
        cropped = masked[y : y + ch, x : x + cw]
        return cropped, (x, y, cw, ch)

    return masked, None
