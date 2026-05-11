# Workflow and Metadata Traceability Matrix

Coverage status scale:

- `Done`: issue state closed and covered by docs.
- `Partial`: implementation/work exists but issue still open or duplicate uncertainty.
- `Gap`: open issue with insufficient explicit documentation linkage.

## Core workflow/metadata features

| Issue | Title | State | Coverage | Primary doc |
|---|---|---|---|---|
| #21 | [Feature][MVP] Metadata Management | Open | Partial | `workflow_catalog.md` (WF-04) |
| #35 | [Feature][MVP] Data Ingestion Pipeline | Open | Partial | `upload_ingestion_flow.md` |
| #42 | [Feature][MVP] Data Validation and Error Handling | Open | Partial | `upload_ingestion_flow.md`, `inference_flow.md` |
| #49 | [Feature][PoC] Minimal Metadata Capture | Open | Partial | `workflow_catalog.md` (WF-04) |
| #50 | [Feature][PoC] Manual Data Submission Workflow | Closed | Done | `upload_ingestion_flow.md` |
| #51 | [Feature][MVP] Structured Upload Workflow with Metadata | Open | Partial | `upload_ingestion_flow.md`, `workflow_catalog.md` |
| #52 | [Feature][MVP] Batch Image Upload Support | Open | Partial | `upload_ingestion_flow.md` |
| #53 | [Feature][MVP] Input Standardisation and Validation at Collection | Open | Partial | `upload_ingestion_flow.md` |

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
| #67 | Define structured upload format and required metadata fields | Open | Gap | Requires final schema alignment sign-off. |
| #68 | Implement structured input interface for image and metadata upload | Closed | Done | Covered by WF-03/WF-04. |
| #69 | Enforce validation and required fields in upload workflow | Closed | Done | Covered by validation/failure handling. |
| #70 | Test and document structured upload workflow | Open | Partial | Baseline doc exists; test evidence still pending. |

## Validation/logging task chain

| Issue | Title | State | Coverage | Notes |
|---|---|---|---|---|
| #19 | Implement validation and error handling for uploads | Closed | Done | Covered by WF-03 failure handling. |
| #38 | Implement validation, error handling, and logging | Open | Partial | Suspected duplicate legacy item without labels/milestone. |
| #39 | Implement validation, error handling, and logging | Open | Partial | Branch `feature/task-39-validation-error-logging` addresses core backend path. |
| #41 | Test and document ingestion pipeline workflow | Open | Done | End-to-end and invalid-batch coverage in `03_application/tests/backend/test_ingestion_pipeline_workflow.py`; workflow documented in `upload_ingestion_flow.md`. |
| #74 | Test and document batch upload workflow | Open | Partial | Suspected duplicate with #75. |
| #75 | Test and document batch upload workflow | Open | Partial | Documentation baseline added; test evidence pending. |
| #81 | Test and document input standardisation and validation workflow | Open | Partial | Validation docs present; final test evidence pending. |

## Recommended cleanup actions (issue hygiene)

- Resolve duplicates explicitly: `#59` vs `#60`, `#38` vs `#39`, `#74` vs `#75`.
- Add acceptance evidence comments for open documentation-test tasks (`#41`, `#70`, `#75`, `#81`).
- After metadata PR merge, reference `docs/metadata/schema/metadata.schema.json` in issue `#22` and `#67`.
