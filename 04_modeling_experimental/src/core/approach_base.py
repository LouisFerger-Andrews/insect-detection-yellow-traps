"""Base interface for interchangeable CV approaches."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class RunContext:
    project: str
    approach: str
    run_dir: Path
    config: Dict[str, Any]


class BaseApproach(ABC):
    """Abstract base class for CV approaches."""

    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx

    @abstractmethod
    def prepare_data(self) -> None:
        """Prepare or export dataset formats for the approach."""

    @abstractmethod
    def train(self) -> None:
        """Train a model (placeholder for real training)."""

    @abstractmethod
    def evaluate(self) -> Dict[str, float]:
        """Evaluate model and return metrics."""

    @abstractmethod
    def predict(self, image_path: Path) -> List[Dict[str, Any]]:
        """Run inference and return detections."""

    @abstractmethod
    def export(self) -> Path:
        """Export model or artifacts and return export path."""
