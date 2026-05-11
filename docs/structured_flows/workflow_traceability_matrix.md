# Workflow and Metadata Traceability Matrix

Coverage status scale:

- `Done`: issue state closed and covered by docs.
- `Partial`: implementation/work exists but issue still open or duplicate uncertainty.
- `Gap`: open issue with insufficient explicit documentation linkage.

## Core workflow/metadata features

| Issue | Title | State | Coverage | Primary doc |
|---|---|---|---|---|
| #21 | [Feature][MVP] Metadata Management | Open | Partial | `workflow_catalog.md` (WF-04) |
| #28 | [Feature][MVP] Prediction Result Storage | Open | Done | `prediction_result_storage_flow.md` |
| #35 | [Feature][MVP] Data Ingestion Pipeline | Open | Partial | `upload_ingestion_flow.md` |
| #42 | [Feature][MVP] Data Validation and Error Handling | Open | Partial | `upload_ingestion_flow.md`, `inference_flow.md` |
| #43 | [Feature][MVP] Storage Structure and Organization | Open | Done | `storage_organization_flow.md` |
| #49 | [Feature][PoC] Minimal Metadata Capture | Open | Partial | `workflow_catalog.md` (WF-04) |
| #50 | [Feature][PoC] Manual Data Submission Workflow | Closed | Done | `upload_ingestion_flow.md` |
| #51 | [Feature][MVP] Structured Upload Workflow with Metadata | Open | Done | `upload_ingestion_flow.md`, `workflow_catalog.md`, `docs/metadata/rules/structured-upload-format.md` |
| #52 | [Feature][MVP] Batch Image Upload Support | Open | Done | `upload_ingestion_flow.md` |
| #53 | [Feature][MVP] Input Standardisation and Validation at Collection | Open | Done | `docs/metadata/rules/collection-input-standards.md` |

## Metadata task chain

| Issue | Title | State | Coverage | Notes |
|---|---|---|---|---|
| #22 | Define metadata schema | Open | Gap | Schema docs exist in `docs/metadata/` branch; align in main after PR merge. |
| #23 | Implement metadata storage in backend | Closed | Done | Covered by WF-04 and ingestion sequence. |
| #24 | Integrate metadata capture in upload workflow | Closed | Done | Covered by WF-03/WF-04 linkage. |
| #25 | Implement metadata retrieval functionality | Closed | Partial | Retrieval path noted; add dedicated retrieval flow if expanded. |
| #26 | Implement metadata validation and consistency checks | Closed | Done | Covered by validation handling sections. |
| #27 | Test and document metadata management workflow | Closed | Done | This matrix + catalog satisfy documentation baseline. |
| #58 | Define minimal metadata fields and structure | Closed | Done | Covered by WF-04 definition section. |
| #59 | Implement metadata input in upload interface | Open | Partial | Potential duplicate with #60. |
| #60 | Implement metadata input in upload interface | Closed | Done | Covered; keep as canonical completion. |
| #61 | Integrate metadata with upload and backend pipeline | Closed | Done | Captured in WF-03 sequence. |
| #62 | Test and document metadata capture workflow | Closed | Done | Covered by matrix and ingestion flow. |
| #67 | Define structured upload format and required metadata fields | Open | Done | MVP multipart format documented in `docs/metadata/rules/structured-upload-format.md`. |
| #68 | Implement structured input interface for image and metadata upload | Closed | Done | Upload UI collects field/trap mode, date range, and image files; exact-trap and field-level paths covered by frontend tests. |
| #69 | Enforce validation and required fields in upload workflow | Closed | Done | Frontend and backend enforce required metadata, image constraints, trap consistency, and date rules before persistence. |
| #70 | Test and document structured upload workflow | Open | Done | Exact-trap structured metadata, field-level batch metadata, frontend submission shape, and validation failures covered in tests and workflow docs. |

## Prediction result task chain

| Issue | Title | State | Coverage | Notes |
|---|---|---|---|---|
| #29 | Define prediction result schema and structure | Open | Done | `trap_uploads` summary and `detections` row structure documented in `prediction_result_storage_flow.md`. |
| #30 | Implement backend storage for prediction results | Open | Done | Backend stores detection rows with `upload_id`, `class_id`, `confidence`, and `bbox_xyxy` coordinates split into columns. |
| #31 | Integrate prediction storage into inference pipeline | Open | Done | Upload ingestion runs inference and stores upload summary plus detections in one SQL transaction. |
| #32 | Implement retrieval of prediction results with images and metadata | Open | Done | `GET /api/analysis/uploads/{upload_id}` returns image metadata with stored detections and ownership checks. |
| #33 | Test and document prediction result storage workflow | Open | Done | Ingestion and retrieval tests cover prediction storage, linkage, retrieval, and access control. |

## Storage organization task chain

| Issue | Title | State | Coverage | Notes |
|---|---|---|---|---|
| #44 | Design storage structure and organisation model | Open | Done | Hierarchical model documented as `<UPLOAD_DIR>/<field_id>/<YYYY>/<MM>/<DD>/<trap_code>/<uuid>_<filename>`. |
| #45 | Define and implement naming conventions for stored data | Open | Done | Storage segments and filenames are sanitized in `upload_service.py`; documented in `storage_organization_flow.md`. |
| #46 | Apply storage structure across images, metadata, and predictions | Open | Done | Uploads persist `image_path`, detections link by `upload_id`, and graph links use committed upload metadata. |
| #47 | Test and document storage structure and organisation | Open | Done | Service and ingestion tests verify hierarchy, SQL path traceability, detections, and graph linkage. |

## Input standardisation task chain

| Issue | Title | State | Coverage | Notes |
|---|---|---|---|---|
| #76 | Define input standards and validation rules at collection | Open | Done | Image, metadata, normalization, and feedback standards documented in `docs/metadata/rules/collection-input-standards.md`. |
| #77 | Implement validation logic in frontend and upload workflow | Open | Done | Frontend validator blocks invalid dates/files/trap context before upload submission. |
| #80 | Enforce standardised formats and constraints during submission | Open | Done | Backend normalizes and validates identifiers, trap codes, date order, batch files, and trap metadata consistency. |
| #81 | Test and document input standardisation and validation workflow | Open | Done | Frontend/backend tests and automated coverage notes added to `collection-input-standards.md`. |

## Batch upload task chain

| Issue | Title | State | Coverage | Notes |
|---|---|---|---|---|
| #71 | Implement batch image selection and upload in frontend | Open | Done | Frontend supports multiple selected images and field-level batch mode; covered by `DashboardPage.test.tsx`. |
| #72 | Implement backend handling for batch image uploads | Open | Done | Backend accepts multi-image requests, enforces a 50-image cap, and commits SQL rows only after all images process successfully. |
| #73 | Ensure metadata association and processing for batch uploads | Open | Done | Shared field metadata and optional per-image capture dates are validated and stored per upload. |
| #75 | Test and document batch upload workflow | Open | Done | Batch E2E, failure, rollback, metadata, and frontend preparation tests are referenced in `upload_ingestion_flow.md`. |

## Validation/logging task chain

| Issue | Title | State | Coverage | Notes |
|---|---|---|---|---|
| #19 | Implement validation and error handling for uploads | Closed | Done | Covered by WF-03 failure handling. |
| #38 | Implement validation, error handling, and logging | Open | Partial | Suspected duplicate legacy item without labels/milestone. |
| #39 | Implement validation, error handling, and logging | Open | Partial | Branch `feature/task-39-validation-error-logging` addresses core backend path. |
| #41 | Test and document ingestion pipeline workflow | Open | Done | End-to-end and invalid-batch coverage in `03_application/tests/backend/test_ingestion_pipeline_workflow.py`; workflow documented in `upload_ingestion_flow.md`. |
| #74 | Test and document batch upload workflow | Open | Partial | Suspected duplicate with #75. |
| #75 | Test and document batch upload workflow | Open | Done | Covered by batch task chain and `upload_ingestion_flow.md` automated coverage. |
| #81 | Test and document input standardisation and validation workflow | Open | Partial | Validation docs present; final test evidence pending. |

## Recommended cleanup actions (issue hygiene)

- Resolve duplicates explicitly: `#59` vs `#60`, `#38` vs `#39`, `#74` vs `#75`.
- Add acceptance evidence comments for open documentation-test tasks (`#41`, `#70`, `#75`, `#81`).
- After metadata PR merge, reference `docs/metadata/schema/metadata.schema.json` in issue `#22` and `#67`.
