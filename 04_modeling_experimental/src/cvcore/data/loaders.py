from pathlib import Path
from typing import Any

from .datasets import COCODetectionDataset


def build_dataloader(dataset: Any, batch_size: int, shuffle: bool = True):
    try:
        from torch.utils.data import DataLoader
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PyTorch is required for DataLoader") from exc

    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


def build_coco_dataset(root: str | Path, annotation_file: str | Path, transforms=None):
    return COCODetectionDataset(root=root, annotation_file=annotation_file, transforms=transforms)
