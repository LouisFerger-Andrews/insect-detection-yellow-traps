# Upload and Ingestion Flow

## Goal
Ingest trap images and metadata into persistent storage and graph/database links.

## Preconditions
- Authenticated user
- Valid field/trap context
- Image and metadata pass validation

## Sequence
1. Client submits upload-range request with one or more images and capture metadata.
2. API validates request dates, batch size, metadata consistency, and file constraints.
3. API resolves and authorizes the field/trap context.
4. API pre-validates every image in the batch before any file is saved or prediction runs.
5. Service saves each image file to upload storage.
6. Inference service runs detection on each saved image.
7. API persists all upload + detection rows in one SQL transaction.
8. Graph service links each committed upload to the field/trap timeline.
9. Optional environmental sync backfills context.

## Batch upload behavior

- Users can submit a single image or a batch of up to 50 images in one request.
- Exact-trap uploads send `field_id`, `trap_id`, and `trap_code`; the API verifies that the field and trap match before processing.
- Field-level batch uploads are supported when exact trap placement is not known. These requests send `field_id` with no `trap_id` and use a field-level `trap_code`, currently `FIELD_BATCH` from the frontend.
- Shared metadata applies to the whole batch: field context, trap context when present, and date range.
- Capture dates are stored per image. By default, dates are allocated across `start_date` to `end_date` in image order.
- Optional `capture_dates` form values can provide one explicit capture date per image. The API rejects mismatched counts and dates outside the submitted range.

## Stored records
- `trap_uploads`: user, field/trap metadata, capture date, saved image path, detection count, average confidence.
- `detections`: one row per predicted object with class, confidence, and `bbox_xyxy` coordinates.
- Graph upload link: field/timeline relationship for monitoring views.

## Automated coverage
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_runs_ingestion_end_to_end`
  verifies upload -> processing -> storage -> prediction serialization -> graph link -> environment sync.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_rejects_invalid_batch_before_storage`
  verifies invalid batch input returns a controlled HTTP 400 before file storage, inference, graph linking, or SQL upload persistence.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_rejects_oversized_batch_before_processing`
  verifies batches over the supported limit are rejected before inference.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_rolls_back_sql_when_batch_processing_fails`
  verifies a mid-batch processing failure does not persist partial SQL upload or detection rows.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_uses_explicit_capture_dates_for_per_image_metadata`
  verifies explicit per-image capture dates remain linked to the correct uploads, field, and graph calls.
- `03_application/frontend/src/pages/__tests__/DashboardPage.test.tsx`
  verifies multiple selected images are submitted together and field-level batch uploads do not require exact trap placement.

## Failure handling
- Validation errors -> HTTP 400 with field-level reason.
- Field/trap permission issues -> HTTP 403/404.
- Batch size greater than 50 images -> HTTP 400 before storage or inference.
- Inference/storage failures -> HTTP 500 with server logs and SQL rollback before any partial rows are committed.
- Environmental sync failures are logged but do not fail a completed upload.
