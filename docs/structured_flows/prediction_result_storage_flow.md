# Prediction Result Storage Flow

## Goal

Store model prediction outputs with the uploaded image and metadata that produced them, then expose the stored result for downstream analysis and review.

## Stored structure

Prediction output is split across upload-level metadata and detection-level rows.

### Upload summary

Stored in `trap_uploads`:

| Field | Meaning |
|---|---|
| `id` | Stable upload identifier used by detections and retrieval endpoints |
| `user_id` | Owner of the upload |
| `field_id` | Field associated with the image |
| `trap_id` | Exact trap marker when known; `null` for field-level batches |
| `trap_code` | Exact trap code or field-level batch code |
| `capture_date` | Image capture date |
| `image_path` | Stored image path in the configured upload hierarchy |
| `detection_count` | Number of prediction rows stored for the image |
| `confidence_avg` | Mean confidence across detections, or `0.0` when no detections are returned |

### Detection rows

Stored in `detections`:

| Field | Meaning |
|---|---|
| `upload_id` | Foreign key to `trap_uploads.id` |
| `class_id` | Model class identifier |
| `confidence` | Model confidence score |
| `x1`, `y1`, `x2`, `y2` | Bounding box coordinates in `bbox_xyxy` order |

## Sequence

1. Upload endpoint saves the validated image file.
2. Inference service returns detections as `class_id`, `confidence`, and `bbox_xyxy`.
3. Upload row is created with image metadata, image path, detection count, and average confidence.
4. One detection row is created for each model output and linked through `upload_id`.
5. The batch SQL transaction commits only after every image has processed successfully.
6. `GET /api/analysis/uploads/{upload_id}` retrieves one upload with its image metadata and stored detections.

## Retrieval behavior

- Admin users can retrieve any upload prediction detail.
- Non-admin users can retrieve only their own uploads.
- Missing or unauthorized uploads return HTTP 404.
- The detail response includes the same detection shape used by upload responses:

```json
{
  "class_id": 0,
  "confidence": 0.8,
  "bbox_xyxy": [1.0, 2.0, 3.0, 4.0]
}
```

## Automated coverage

- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_runs_ingestion_end_to_end`
  verifies inference outputs are stored as upload summary values and detection rows.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_upload_range_persists_structured_exact_trap_metadata`
  verifies detections remain linked to the upload and metadata.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_get_upload_prediction_result_returns_image_metadata_and_detections`
  verifies retrieval returns image metadata plus complete detection details.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py::test_get_upload_prediction_result_enforces_upload_ownership`
  verifies retrieval access control.
