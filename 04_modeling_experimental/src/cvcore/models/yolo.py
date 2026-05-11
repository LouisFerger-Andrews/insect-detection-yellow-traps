from typing import Any, Dict, List

from .base import Model


class YoloModel(Model):
    def __init__(self, yolo: Any):
        self.yolo = yolo

    def train(self, train_loader, val_loader=None) -> Dict[str, Any]:
        raise NotImplementedError("Use YOLO training entrypoints")

    def predict(self, batch) -> List[Dict[str, Any]]:
        return self.yolo(batch)

    def save(self, path: str) -> None:
        self.yolo.save(path)

    def load(self, path: str) -> "YoloModel":
        self.yolo.load(path)
        return self
