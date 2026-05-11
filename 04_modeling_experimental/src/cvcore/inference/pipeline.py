from pathlib import Path
from typing import Any, Dict


class InferencePipeline:
    def __init__(self, model: Any):
        self.model = model

    def predict_image(self, image_path: str) -> Dict[str, Any]:
        try:
            import cv2
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("OpenCV is required for inference pipeline") from exc

        img = cv2.imread(image_path)
        preds = self.model.predict([img])
        return {"image": image_path, "pred": preds[0]}

    def predict_batch(self, input_dir: str, out_dir: str) -> None:
        in_path = Path(input_dir)
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        for img_path in in_path.glob("*.jpg"):
            pred = self.predict_image(str(img_path))
            out_file = out_path / f"{img_path.stem}.txt"
            with out_file.open("w", encoding="utf-8") as f:
                f.write(str(pred))
