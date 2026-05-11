# Storage Organization Flow

## Goal

Define how uploaded images, metadata, and prediction results are organized so stored data remains traceable as the dataset grows.

## Image storage hierarchy

Uploaded image files are stored under the configured `UPLOAD_DIR`, which defaults to `storage/uploads`.

Path template:

```text
<UPLOAD_DIR>/<field_id>/<YYYY>/<MM>/<DD>/<trap_code>/<uuid>_<sanitized_original_filename>
```

Example:

```text
storage/uploads/field-ingestion/2026/05/01/North-Edge/4f2c..._structured-trap.jpg
```

## Naming conventions

- `field_id` directory segment uses the resolved field identifier.
- Date directory segments use the stored `capture_date`.
- `trap_code` directory segment uses the resolved exact-trap code or the field-level batch code.
- Spaces in path segments are converted to hyphens.
- Path segment characters outside letters, numbers, underscores, or hyphens are removed.
- Stored filenames use a generated UUID prefix plus the sanitized original filename.
- Original filename sanitization preserves letters, numbers, `.`, `-`, and `_`.

## Traceability

Each stored image is linked through the following chain:

1. File path is persisted in `trap_uploads.image_path`.
2. Upload metadata is persisted in `trap_uploads` with `user_id`, `field_id`, optional `trap_id`, `trap_code`, and `capture_date`.
3. Prediction results are persisted in `detections` rows linked by `detections.upload_id`.
4. Graph links connect the committed upload ID to the field timeline using field, upload ID, capture date, and detection count.
5. Analytics and environmental sync retrieve uploads by SQL metadata such as field, trap, and capture date.

## Failure behavior

- Invalid files are rejected before storage or inference.
- If processing fails before the SQL transaction commits, saved files from that failed batch are removed.
- SQL upload and detection rows are committed only after all images in the batch process successfully.

## Automated coverage

- `03_application/tests/backend/test_upload_service.py::test_save_upload_file_uses_hierarchical_storage_context`
  verifies the hierarchical path and sanitized naming convention.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_runs_ingestion_end_to_end`
  verifies batch images are stored under field/date/trap directories and `trap_uploads.image_path` points to the saved files.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_persists_structured_exact_trap_metadata`
  verifies exact-trap metadata, stored image path, detections, and graph link remain traceable to the same upload.
