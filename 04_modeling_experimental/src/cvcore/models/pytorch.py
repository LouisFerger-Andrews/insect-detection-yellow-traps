from typing import Any, Dict, List

from .base import Model


class TorchDetectionModel(Model):
    def __init__(self, model: Any):
        self.model = model

    def train(self, train_loader, val_loader=None) -> Dict[str, Any]:
        raise NotImplementedError("Training loop should be implemented in Trainer")

    def predict(self, batch) -> List[Dict[str, Any]]:
        return self.model(batch)

    def save(self, path: str) -> None:
        try:
            import torch
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PyTorch is required to save models") from exc
        torch.save(self.model.state_dict(), path)

    def load(self, path: str) -> "TorchDetectionModel":
        try:
            import torch
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PyTorch is required to load models") from exc
        self.model.load_state_dict(torch.load(path, map_location="cpu"))
        return self
