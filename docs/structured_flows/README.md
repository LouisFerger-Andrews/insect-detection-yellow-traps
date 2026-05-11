# Structured Flows

This folder documents end-to-end operational flows for the insect identification platform.

## Included docs

- `workflow_catalog.md`: major workflows and ownership boundaries
- `workflow_traceability_matrix.md`: issue-to-documentation coverage (open + closed)
- `upload_ingestion_flow.md`: upload, validation, ingestion, persistence
- `metadata_lifecycle_flow.md`: metadata definition-to-audit lifecycle
- `storage_organization_flow.md`: upload storage hierarchy, naming, traceability
- `inference_flow.md`: model loading and prediction path
- `analytics_flow.md`: aggregation and reporting path

## Documentation standard

Each flow should define:

- scope and preconditions
- sequence of steps
- output/state changes
- failure handling and expected errors
