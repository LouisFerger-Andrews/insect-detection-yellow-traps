from __future__ import annotations

from cvcore.inference.postprocess import nms


def test_nms_returns_input_for_now() -> None:
    preds = [{"bbox": [0, 0, 10, 10], "score": 0.9}]
    assert nms(preds, iou_thresh=0.4) == preds

