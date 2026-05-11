"""Evaluation metrics stubs."""
from __future__ import annotations

from typing import Dict, List


def mean_average_precision(detections: List[dict], targets: List[dict]) -> float:
    """Placeholder mAP computation."""
    if not targets:
        return 0.0
    return 0.0


def counting_error(detections: List[dict], targets: List[dict]) -> float:
    """Absolute counting error placeholder."""
    return abs(len(detections) - len(targets))


def summarize_metrics(detections: List[dict], targets: List[dict]) -> Dict[str, float]:
    return {
        "mAP": mean_average_precision(detections, targets),
        "count_error": counting_error(detections, targets),
    }
