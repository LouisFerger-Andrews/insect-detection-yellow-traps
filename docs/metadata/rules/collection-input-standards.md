# Collection Input Standards

These standards define the accepted input shape at the point of collection for trap image uploads.

## Image files

| Rule | Standard |
|---|---|
| Accepted formats | `.jpg`, `.jpeg`, `.png`, `.webp` |
| Maximum size | 20 MB per image |
| Empty files | Rejected |
| Dataset images | Filenames containing training, validation, or test dataset markers are rejected |
| Batch behavior | Every file in a batch must pass validation before processing starts |

Dataset marker rejection prevents accidental upload of model training, validation, or test assets into production monitoring data.

## Required upload metadata

| Field | Format | Constraint |
|---|---|---|
| `field_id` | system field identifier | Required unless `trap_id` is provided |
| `trap_id` | system trap identifier | Required for the frontend upload workflow |
| `trap_code` | trap display/code value | Required, 1-64 characters, letters/numbers/underscore/hyphen/space |
| `start_date` | ISO date, `YYYY-MM-DD` | Required |
| `end_date` | ISO date, `YYYY-MM-DD` | Required, must be on or after `start_date` |
| `images` | one or more image files | Required |

The API resolves `field_id` and `trap_code` from `trap_id` when a trap is provided. Frontend collection still submits all three values so the request is explicit and traceable.

## Normalization

- Uploaded filenames are sanitized before storage.
- `field_id`, `trap_id`, and `trap_code` are trimmed before validation.
- Stored filenames use a generated unique prefix plus the sanitized original filename.
- Capture dates are allocated across the submitted date range in image order.

## User feedback

- Frontend validation blocks submission before network upload when required inputs, dates, or file formats are invalid.
- Backend validation returns HTTP 400 with a clear reason when submitted data violates the standard.
- Internal storage, inference, and integration failures return a controlled HTTP 500 and are logged server-side.

## Automated coverage

- `03_application/frontend/src/utils/__tests__/uploadValidation.test.ts` verifies frontend validation for valid uploads, date order, unsupported extensions, dataset filenames, empty files, and missing trap context.
- `03_application/frontend/src/pages/__tests__/DashboardPage.test.tsx` verifies the upload form blocks non-standard files before submission.
- `03_application/tests/backend/test_upload_service.py` verifies backend upload file, identifier, and trap-code validation helpers.
- `03_application/tests/backend/test_ingestion_pipeline_workflow.py` verifies invalid batches and inconsistent trap metadata do not reach storage or inference.
