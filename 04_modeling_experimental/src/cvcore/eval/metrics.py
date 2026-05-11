from typing import List


def count_mae(pred_counts: List[int], gt_counts: List[int]) -> float:
    if len(pred_counts) != len(gt_counts):
        raise ValueError("Prediction and ground truth lengths must match")
    return sum(abs(p - g) for p, g in zip(pred_counts, gt_counts)) / max(1, len(gt_counts))
