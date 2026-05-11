"""Approach registry."""
from __future__ import annotations

from typing import Dict, Type

from core.approach_base import BaseApproach
from approaches.classical_cv.approach import ClassicalCVApproach
from approaches.rtdetr.approach import RTDETRApproach
from approaches.yolo.approach import YoloApproach


APPROACH_REGISTRY: Dict[str, Type[BaseApproach]] = {
    "yolo": YoloApproach,
    "rtdetr": RTDETRApproach,
    "classical_cv": ClassicalCVApproach,
}


def list_approaches() -> Dict[str, Type[BaseApproach]]:
    return dict(APPROACH_REGISTRY)


def get_approach(name: str) -> Type[BaseApproach]:
    if name not in APPROACH_REGISTRY:
        raise KeyError(
            f"Unknown approach '{name}'. Available: {', '.join(APPROACH_REGISTRY)}"
        )
    return APPROACH_REGISTRY[name]
