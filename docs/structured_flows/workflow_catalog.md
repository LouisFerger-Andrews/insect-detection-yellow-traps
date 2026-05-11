# Workflow Catalog (Major SDLC Flows)

This document lists the major operational workflows in the insect identification system and points to the detailed flow docs.

## WF-01 Authentication and Access Control

- Scope: registration, login, token validation, role-based access.
- Backend entry points: `app/api/auth.py`, `app/api/deps.py`.
- Risks: invalid tokens, unauthorized field access.
- Status: documented at high-level in traceability matrix.

## WF-02 Field and Trap Management

- Scope: field creation, trap mapping, trap metadata updates.
- Backend entry points: `app/api/fields.py`, `app/api/map.py`.
- Risks: ownership validation, map consistency.
- Status: documented at high-level in traceability matrix.

## WF-03 Upload and Ingestion

- Scope: image upload, file validation, persistence, graph links.
- Detailed docs: `upload_ingestion_flow.md`, `../metadata/rules/structured-upload-format.md`.
- Related issue cluster: `#48`, `#50`, `#51`, `#52`, `#35` + task chains.

## WF-04 Metadata Lifecycle

- Scope: metadata schema, input capture, validation, storage, retrieval.
- Related docs: `upload_ingestion_flow.md`, `workflow_traceability_matrix.md`, plus metadata docs in `docs/metadata/` (other branch).
- Related issue cluster: `#21`, `#22`-`#27`, `#49`, `#58`-`#62`, `#67`-`#70`.

## WF-05 Inference and Detection

- Scope: model loading, prediction execution, detection serialization.
- Detailed doc: `inference_flow.md`.
- Related issue cluster: `#35`, `#39`, `#42`.

## WF-06 Analytics and Reporting

- Scope: upload/detection aggregations, trend metrics, exploratory chat context.
- Detailed doc: `analytics_flow.md`.
- Related issue cluster: `#6` epic direction + analytics APIs.

## WF-07 Environmental Data Sync

- Scope: weather/environment enrichment and date-range sync.
- Backend entry points: `app/api/environment.py`, `app/services/environment_service.py`.
- Status: documented at high-level in traceability matrix.

## WF-08 Admin and Operational Oversight

- Scope: admin data inspection, quality checks, operational visibility.
- Backend entry points: `app/api/admin.py`.
- Status: documented at high-level in traceability matrix.

## Documentation quality criteria

- Every major workflow must define: preconditions, sequence, outputs, and failure handling.
- Every workflow-related issue should map to at least one doc section.
- Open workflow/metadata tasks should be explicitly marked as partial/remaining in the traceability matrix.
