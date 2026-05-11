"""Dataset loading helpers."""
from __future__ import annotations

from pathlib import Path
from typing import List


def list_images(raw_images_dir: Path, image_glob: str) -> List[Path]:
    if not raw_images_dir.exists():
        return []
    return sorted(raw_images_dir.glob(image_glob))


def ensure_raw_images(raw_images_dir: Path, image_glob: str) -> List[Path]:
    images = list_images(raw_images_dir, image_glob)
    if not images:
        raise FileNotFoundError(
            f"No raw images found at {raw_images_dir} with glob '{image_glob}'."
        )
    return images
