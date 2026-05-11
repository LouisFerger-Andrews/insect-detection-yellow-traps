from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import json


class DatasetAdapter(ABC):
    @abstractmethod
    def __len__(self) -> int: ...

    @abstractmethod
    def __getitem__(self, idx: int) -> Dict[str, Any]: ...

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]: ...


class COCODetectionDataset(DatasetAdapter):
    def __init__(
        self,
        root: str | Path,
        annotation_file: str | Path,
        transforms: Optional[Any] = None,
        load_images: bool = True,
    ):
        self.root = Path(root)
        self.annotation_path = Path(annotation_file)
        if not self.annotation_path.is_absolute():
            self.annotation_path = self.root / self.annotation_path
        if not self.annotation_path.exists():
            raise FileNotFoundError(f"Missing annotation file: {self.annotation_path}")

        self.images_dir = self.annotation_path.parent
        self.transforms = transforms
        self.load_images = load_images

        with self.annotation_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.images = sorted(data.get("images", []), key=lambda x: x.get("id", 0))
        self.annotations = data.get("annotations", [])
        self.categories = data.get("categories", [])

        self._anns_by_image: Dict[int, List[Dict[str, Any]]] = {
            img["id"]: [] for img in self.images
        }
        for ann in self.annotations:
            self._anns_by_image.setdefault(ann["image_id"], []).append(ann)

        self._class_map = {c["id"]: c.get("name", str(c["id"])) for c in self.categories}

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        info = self.images[idx]
        img_path = self.images_dir / info["file_name"]
        if not img_path.exists():
            raise FileNotFoundError(f"Missing image: {img_path}")

        image = img_path
        if self.load_images:
            try:
                import cv2
            except Exception as exc:  # pragma: no cover - optional dependency
                raise RuntimeError("OpenCV is required to load images") from exc
            image = cv2.imread(str(img_path))

        sample = {
            "image": image,
            "image_id": info["id"],
            "file_name": info["file_name"],
            "width": info.get("width"),
            "height": info.get("height"),
            "annotations": self._anns_by_image.get(info["id"], []),
        }

        if self.transforms is not None:
            sample = self.transforms(sample)
        return sample

    def get_metadata(self) -> Dict[str, Any]:
        class_names = [self._class_map[c["id"]] for c in self.categories]
        return {
            "num_images": len(self.images),
            "num_classes": len(class_names),
            "class_names": class_names,
        }
