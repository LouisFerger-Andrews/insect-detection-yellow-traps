# Upload and Ingestion Flow

## Goal
Ingest trap images and metadata into persistent storage and graph/database links.

## Preconditions
- Authenticated user
- Valid field/trap context
- Image and metadata pass validation

## Sequence
1. Client submits upload-range request with images and capture range.
2. API validates request dates and file constraints.
3. API resolves and authorizes the field/trap context.
4. API pre-validates every image in the batch before any file is saved or prediction runs.
5. Service saves each image file to upload storage.
6. Inference service runs detection on each saved image.
7. API persists upload + detections in SQL store.
8. Graph service links each upload to the field/trap timeline.
9. Optional environmental sync backfills context.

## Stored records
- `trap_uploads`: user, field/trap metadata, capture date, saved image path, detection count, average confidence.
- `detections`: one row per predicted object with class, confidence, and `bbox_xyxy` coordinates.
- Graph upload link: field/timeline relationship for monitoring views.

## Automated coverage
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_runs_ingestion_end_to_end`
  verifies upload -> processing -> storage -> prediction serialization -> graph link -> environment sync.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_rejects_invalid_batch_before_storage`
  verifies invalid batch input returns a controlled HTTP 400 before file storage, inference, graph linking, or SQL upload persistence.

## Failure handling
- Validation errors -> HTTP 400 with field-level reason.
- Field/trap permission issues -> HTTP 403/404.
- Inference/storage failures -> HTTP 500 with server logs.
- Environmental sync failures are logged but do not fail a completed upload.
