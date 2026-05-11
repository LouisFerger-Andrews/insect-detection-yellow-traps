from typing import Dict, List

from .base import Model


class OpenCVDetector(Model):
    def __init__(self, threshold: int = 150):
        self.threshold = threshold

    def train(self, train_loader, val_loader=None) -> Dict[str, float]:
        return {"status": "no_train"}

    def predict(self, batch) -> List[Dict[str, float]]:
        try:
            import cv2
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("OpenCV is required for classical baseline") from exc

        outputs = []
        for img in batch:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
            count = int(mask.mean() > 0)
            outputs.append({"count": count})
        return outputs

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(self.threshold))

    def load(self, path: str) -> "OpenCVDetector":
        with open(path, "r", encoding="utf-8") as f:
            self.threshold = int(f.read().strip())
        return self
