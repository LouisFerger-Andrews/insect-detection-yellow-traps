# Structured Upload Format

This document defines the upload request shape used by the application for image ingestion with metadata.

## Endpoint

`POST /api/analysis/upload-range`

Request content type: `multipart/form-data`

## Required fields

| Field | Type | Required | Constraint |
|---|---|---|---|
| `start_date` | ISO date string | Yes | `YYYY-MM-DD`; must be on or before `end_date` |
| `end_date` | ISO date string | Yes | `YYYY-MM-DD`; must be on or after `start_date` |
| `field_id` | string | Yes unless exact `trap_id` resolves the field | 1-64 characters; letters, numbers, underscores, or hyphens |
| `trap_code` | string | Yes | 1-64 characters; letters, numbers, spaces, underscores, or hyphens |
| `images` | repeated file field | Yes | 1-50 files; each file must pass image validation |

## Conditional fields

| Field | Type | Required when | Constraint |
|---|---|---|---|
| `trap_id` | string | Exact-trap upload mode | Must identify a trap in the resolved field |
| `capture_dates` | repeated ISO date string | Optional | If provided, exactly one date per image and each date must fall within `start_date` to `end_date` |

## Upload modes

### Exact-Trap Upload

Use this when every image belongs to a known trap marker.

Required metadata:

- `field_id`
- `trap_id`
- `trap_code`
- `start_date`
- `end_date`
- `images`

The backend resolves the trap, verifies field ownership, confirms `field_id` and `trap_code` match the selected trap, and stores each image with the resolved field, trap, trap code, capture date, image path, detection count, and confidence average.

### Field-Level Batch Upload

Use this when images belong to a field but exact trap placement is not known at upload time.

Required metadata:

- `field_id`
- `trap_code`, currently submitted by the frontend as `FIELD_BATCH`
- `start_date`
- `end_date`
- `images`

`trap_id` is omitted. The backend stores the uploads against the field with `trap_id = null` and the submitted field-level `trap_code`.

## Image constraints

| Rule | Standard |
|---|---|
| Accepted formats | `.jpg`, `.jpeg`, `.png`, `.webp` |
| Maximum file size | 20 MB per image |
| Batch size | 1-50 images |
| Empty files | Rejected |
| Dataset guard | Filenames containing training, validation, or test dataset markers are rejected |

Every image in the batch is validated before storage or inference starts.

## Date handling

- Without `capture_dates`, the backend allocates capture dates across `start_date` to `end_date` in image order.
- With `capture_dates`, the backend uses the provided per-image dates in image order.
- Invalid date ranges, mismatched per-image date counts, and per-image dates outside the shared range are rejected before processing.

## Persistence mapping

| Request value | Stored target |
|---|---|
| authenticated user | `trap_uploads.user_id` |
| resolved `field_id` | `trap_uploads.field_id` |
| resolved or omitted `trap_id` | `trap_uploads.trap_id` |
| resolved or submitted `trap_code` | `trap_uploads.trap_code` |
| allocated or explicit capture date | `trap_uploads.capture_date` |
| saved file path | `trap_uploads.image_path` |
| inference summary | `trap_uploads.detection_count`, `trap_uploads.confidence_avg` |
| per-detection bounding boxes | `detections` rows linked by `upload_id` |

## Compatibility notes

The canonical metadata schema in `docs/metadata/schema/metadata.schema.json` defines the broader per-image metadata target for future collection maturity. The current MVP structured upload workflow persists the subset required by ingestion, storage, graph linking, prediction, and analytics.
