# Inference Flow

## Goal
Generate insect detections from a captured trap image.

## Preconditions
- Model weights are available and readable.
- Uploaded image exists and has supported format.

## Sequence
1. API passes image path to inference service.
2. Service validates image path and extension.
3. YOLO model is loaded (lazy singleton).
4. Prediction runs with configured confidence and image size.
5. Raw boxes are normalized into `bbox_xyxy`, `confidence`, `class_id`.
6. Detection list is returned to ingestion layer.

## Failure handling
- Missing weights/image -> explicit validation error.
- Runtime model failure -> logged exception + controlled API error.
