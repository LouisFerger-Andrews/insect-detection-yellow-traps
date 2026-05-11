# Metadata Lifecycle Flow

## Goal
Define how metadata is captured, validated, persisted, retrieved, and audited across the insect identification workflow.

## Lifecycle stages

1. Definition
- Canonical fields are defined in schema docs (`docs/metadata/` branch).
- Required identifiers: `field_id`, `trap_code`, `capture_date`, operator/device context.

2. Capture
- Metadata enters via upload forms/API fields.
- Input should be normalized (trimmed values, stable IDs, valid date/time).

3. Validation
- Required field presence and format checks.
- Logical checks: timestamp consistency, optional geo/weather range checks.
- Reject unknown/unsupported fields to avoid schema drift.

4. Persistence
- Metadata is linked to upload/image records in SQL.
- Related graph links maintain traceability by field/trap/date.

5. Retrieval and Usage
- Metadata is consumed by analytics and reporting endpoints.
- Retrieval must preserve linkage to image and detection records.

6. Audit and Evolution
- Changes to schema require versioning and migration notes.
- Open tasks should track remaining validation/retrieval/documentation gaps.

## Related issues

- Feature: `#21`, `#49`, `#51`
- Tasks: `#22`-`#27`, `#58`-`#62`, `#67`-`#70`

## Current status

- Core flow documented.
- Remaining gap: final schema sign-off and closure of open metadata-definition/testing tasks.
