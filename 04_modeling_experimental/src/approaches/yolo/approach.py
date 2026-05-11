"""YOLO approach stub."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Dict, List

from core.approach_base import BaseApproach
from core.config import parse_common_config
from data.coco import (
    CocoSplitConfig,
    convert_coco_split_to_yolo,
    group_annotations,
    load_coco,
    write_yolo_dataset_yaml,
)
from data.masking import MaskConfig
from utils.logging import get_logger


class YoloApproach(BaseApproach):
    """YOLO approach (Ultralytics)."""

    def prepare_data(self) -> None:
        common = parse_common_config(self.ctx.config)
        data_cfg = self.ctx.config.get("data", {})
        coco_cfg = data_cfg.get("coco", {})
        if not coco_cfg:
            raise ValueError("Missing data.coco config for COCO conversion.")

        mask_cfg = MaskConfig(**data_cfg.get("masking", {}))
        output_dir = common.processed_dir / "yolo"

        splits: List[CocoSplitConfig] = []
        for split_name in ("train", "val", "test"):
            split_data = coco_cfg.get(split_name)
            if not split_data:
                continue
            splits.append(
                CocoSplitConfig(
                    name=split_name,
                    images_dir=Path(split_data["images_dir"]),
                    annotations_path=Path(split_data["annotations_path"]),
                )
            )

        if not splits:
            raise ValueError("No COCO splits configured under data.coco.*")

        class_names: List[str] = []
        for split in splits:
            names = convert_coco_split_to_yolo(split, output_dir, mask_cfg)
            if not class_names:
                class_names = names

        data_yaml = write_yolo_dataset_yaml(
            output_dir,
            class_names,
            train="images/train",
            val="images/val",
            test="images/test" if any(s.name == "test" for s in splits) else None,
        )
        logger = get_logger("yolo", self.ctx.run_dir)
        logger.info("Exported YOLO dataset to %s", data_yaml.parent)

    def _resolve_weights(self) -> str:
        approach_cfg = self.ctx.config.get("approach", {})
        # Prefer weights generated in the current run to avoid accidentally
        # evaluating stale checkpoints from older runs.
        run_best = self.ctx.run_dir / "train" / "weights" / "best.pt"
        if run_best.exists():
            return str(run_best)
        run_weights = self.ctx.run_dir / "train" / "weights" / "last.pt"
        if run_weights.exists():
            return str(run_weights)
        weights = approach_cfg.get("weights")
        if weights:
            return str(weights)
        return str(approach_cfg.get("model", "yolov8n.pt"))

    def _resolve_model_candidates(self) -> List[str]:
        approach_cfg = self.ctx.config.get("approach", {})
        candidates = approach_cfg.get("model_candidates")
        if isinstance(candidates, list) and candidates:
            return [str(item) for item in candidates]
        model_name = approach_cfg.get("model")
        if model_name:
            return [str(model_name)]
        # Latest-first fallback chain for Ultralytics model families.
        return ["yolo26n.pt", "yolo11n.pt", "yolov8n.pt"]

    def _resolve_train_model(self, ultralytics_module: Any) -> Any:
        logger = get_logger("yolo", self.ctx.run_dir)
        errors: List[str] = []
        for candidate in self._resolve_model_candidates():
            try:
                model = ultralytics_module.YOLO(candidate)
                logger.info("Using training model candidate: %s", candidate)
                return model
            except Exception as exc:  # pragma: no cover - depends on runtime/download state
                errors.append(f"{candidate}: {exc}")
        raise RuntimeError(
            "Failed to load any YOLO model candidate. Tried: "
            + ", ".join(self._resolve_model_candidates())
            + ". Errors: "
            + " | ".join(errors)
        )

    def _compute_count_error(
        self,
        model: Any,
        split: CocoSplitConfig,
        imgsz: int,
        conf: float,
        max_images: int,
    ) -> float:
        coco = load_coco(split.annotations_path)
        anns_by_image = group_annotations(coco)
        images = coco.get("images", [])
        if not images:
            return 0.0
        total_error = 0.0
        evaluated = 0
        for image in images[:max_images]:
            image_path = split.images_dir / image["file_name"]
            if not image_path.exists():
                continue
            results = model.predict(
                source=str(image_path), imgsz=imgsz, conf=conf, verbose=False
            )
            pred_count = int(len(results[0].boxes)) if results else 0
            gt_count = int(len(anns_by_image.get(image["id"], [])))
            total_error += abs(pred_count - gt_count)
            evaluated += 1
        if evaluated == 0:
            return 0.0
        return total_error / float(evaluated)

    def _write_metrics_file(self, metrics: Dict[str, float]) -> None:
        eval_cfg = self.ctx.config.get("eval", {})
        output_path = eval_cfg.get("metrics_output_path")
        if output_path:
            target = Path(str(output_path))
        else:
            target = self.ctx.run_dir / "model_metrics.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(metrics, indent=2))

    def train(self) -> None:
        logger = get_logger("yolo", self.ctx.run_dir)
        try:
            ultralytics = importlib.import_module("ultralytics")
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics not installed. Install with: pip install ultralytics"
            ) from exc
        common = parse_common_config(self.ctx.config)
        output_dir = common.processed_dir / "yolo"
        data_yaml = output_dir / "data.yaml"
        if not data_yaml.exists():
            raise FileNotFoundError(
                f"Missing YOLO dataset yaml. Run prepare-data first: {data_yaml}"
            )
        approach_cfg = self.ctx.config.get("approach", {})
        train_cfg = self.ctx.config.get("training", {})

        imgsz = int(approach_cfg.get("img_size", 960))
        epochs = train_cfg.get("epochs", 20)
        batch = train_cfg.get("batch_size", 8)
        model = self._resolve_train_model(ultralytics)

        train_args: Dict[str, Any] = {
            "data": str(data_yaml),
            "epochs": epochs,
            "imgsz": imgsz,
            "batch": batch,
            "project": str(self.ctx.run_dir),
            "name": "train",
            "exist_ok": True,
            # Strong defaults for tiny-object detection on trap imagery.
            "optimizer": train_cfg.get("optimizer", "AdamW"),
            "lr0": train_cfg.get("lr0", 0.001),
            "lrf": train_cfg.get("lrf", 0.01),
            "weight_decay": train_cfg.get("weight_decay", 0.0005),
            "warmup_epochs": train_cfg.get("warmup_epochs", 3.0),
            "patience": train_cfg.get("patience", 50),
            "cos_lr": train_cfg.get("cos_lr", True),
            "close_mosaic": train_cfg.get("close_mosaic", 10),
            "mosaic": train_cfg.get("mosaic", 1.0),
            "mixup": train_cfg.get("mixup", 0.1),
            "copy_paste": train_cfg.get("copy_paste", 0.1),
            "hsv_h": train_cfg.get("hsv_h", 0.015),
            "hsv_s": train_cfg.get("hsv_s", 0.7),
            "hsv_v": train_cfg.get("hsv_v", 0.4),
            "degrees": train_cfg.get("degrees", 0.0),
            "translate": train_cfg.get("translate", 0.1),
            "scale": train_cfg.get("scale", 0.5),
            "shear": train_cfg.get("shear", 0.0),
            "perspective": train_cfg.get("perspective", 0.0),
            "flipud": train_cfg.get("flipud", 0.0),
            "fliplr": train_cfg.get("fliplr", 0.5),
            "single_cls": train_cfg.get("single_cls", True),
            "cache": train_cfg.get("cache", False),
            "amp": train_cfg.get("amp", True),
            "device": train_cfg.get("device", None),
            "workers": train_cfg.get("workers", 8),
        }
        # Ultralytics ignores unknown args poorly in some versions, so filter None.
        train_args = {k: v for k, v in train_args.items() if v is not None}

        logger.info("Training args: %s", train_args)
        model.train(
            **train_args,
        )
        logger.info("Training complete.")

    def evaluate(self) -> Dict[str, float]:
        logger = get_logger("yolo", self.ctx.run_dir)
        try:
            ultralytics = importlib.import_module("ultralytics")
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics not installed. Install with: pip install ultralytics"
            ) from exc
        common = parse_common_config(self.ctx.config)
        output_dir = common.processed_dir / "yolo"
        data_yaml = output_dir / "data.yaml"
        if not data_yaml.exists():
            raise FileNotFoundError(
                f"Missing YOLO dataset yaml. Run prepare-data first: {data_yaml}"
            )
        approach_cfg = self.ctx.config.get("approach", {})
        imgsz = approach_cfg.get("img_size", 640)
        conf = approach_cfg.get("conf", 0.25)
        weights = self._resolve_weights()
        model = ultralytics.YOLO(weights)
        results = model.val(data=str(data_yaml), imgsz=imgsz)
        map50_95 = float(getattr(results.box, "map", 0.0))
        map50 = float(getattr(results.box, "map50", 0.0))
        metrics = {
            "mAP50-95": map50_95,
            "mAP50_95": map50_95,
            "mAP50": map50,
        }
        eval_cfg = self.ctx.config.get("eval", {})
        if eval_cfg.get("compute_count_error", True):
            coco_cfg = self.ctx.config.get("data", {}).get("coco", {})
            val_cfg = coco_cfg.get("val")
            if val_cfg:
                split = CocoSplitConfig(
                    name="val",
                    images_dir=Path(val_cfg["images_dir"]),
                    annotations_path=Path(val_cfg["annotations_path"]),
                )
                max_images = int(eval_cfg.get("max_images", 50))
                metrics["count_error"] = self._compute_count_error(
                    model, split, imgsz, conf, max_images
                )
            else:
                metrics["count_error"] = 0.0
        # Include precision/recall/F1 so model quality is fully visible.
        precision = float(getattr(results.box, "p", [0.0])[0]) if hasattr(results, "box") else 0.0
        recall = float(getattr(results.box, "r", [0.0])[0]) if hasattr(results, "box") else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        metrics["precision"] = precision
        metrics["recall"] = recall
        metrics["f1"] = f1

        self._write_metrics_file(metrics)
        logger.info("Evaluation metrics: %s", metrics)
        return metrics

    def predict(self, image_path: Path) -> List[Dict[str, Any]]:
        logger = get_logger("yolo", self.ctx.run_dir)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        try:
            ultralytics = importlib.import_module("ultralytics")
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics not installed. Install with: pip install ultralytics"
            ) from exc
        approach_cfg = self.ctx.config.get("approach", {})
        imgsz = approach_cfg.get("img_size", 640)
        conf = approach_cfg.get("conf", 0.25)
        weights = self._resolve_weights()
        model = ultralytics.YOLO(weights)
        results = model.predict(
            source=str(image_path), imgsz=imgsz, conf=conf, verbose=False
        )
        detections: List[Dict[str, Any]] = []
        if results:
            for box in results[0].boxes:
                xyxy = box.xyxy[0].tolist()
                detections.append(
                    {
                        "bbox_xyxy": [float(v) for v in xyxy],
                        "conf": float(box.conf[0]),
                        "class_id": int(box.cls[0]),
                    }
                )
        logger.info("Predicted %d detections.", len(detections))
        return detections

    def export(self) -> Path:
        try:
            ultralytics = importlib.import_module("ultralytics")
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics not installed. Install with: pip install ultralytics"
            ) from exc
        approach_cfg = self.ctx.config.get("approach", {})
        export_format = approach_cfg.get("export_format", "onnx")
        imgsz = approach_cfg.get("img_size", 640)
        weights = self._resolve_weights()
        model = ultralytics.YOLO(weights)
        export_result = model.export(format=export_format, imgsz=imgsz)
        export_dir = self.ctx.run_dir / "export"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "export_result.txt").write_text(str(export_result))
        return export_dir
