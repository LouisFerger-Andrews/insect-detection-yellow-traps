from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from cvcore.inference.pipeline import InferencePipeline


class _FakeModel:
    def __init__(self) -> None:
        self.calls = 0

    def predict(self, batch):  # noqa: ANN001
        self.calls += 1
        assert len(batch) == 1
        return [{"detections": 2}]


def test_predict_image_returns_first_prediction(tmp_path: Path) -> None:
    img = np.zeros((16, 16, 3), dtype=np.uint8)
    image_path = tmp_path / "frame.jpg"
    cv2.imwrite(str(image_path), img)

    pipeline = InferencePipeline(model=_FakeModel())
    out = pipeline.predict_image(str(image_path))
    assert out["image"] == str(image_path)
    assert out["pred"] == {"detections": 2}


def test_predict_batch_writes_output_files(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    for name in ("a.jpg", "b.jpg"):
        cv2.imwrite(str(in_dir / name), img)

    pipeline = InferencePipeline(model=_FakeModel())
    pipeline.predict_batch(str(in_dir), str(out_dir))

    assert (out_dir / "a.txt").exists()
    assert (out_dir / "b.txt").exists()

