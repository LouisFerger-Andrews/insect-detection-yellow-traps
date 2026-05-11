# Metadata Validation Rules

## Required fields

- `schema_version`: must be `v1.0.0`
- `field_id`: stable field identifier
- `trap_code`: stable trap identifier within field
- `capture_date`: ISO date (`YYYY-MM-DD`)
- `capture_time`: 24h time (`HH:MM` or `HH:MM:SS`)
- `timezone`: IANA timezone string (`Europe/Berlin`)
- `device_id`: camera or mobile capture device ID
- `operator_id`: user or technician identifier

## Collection upload constraints

- Accepted image extensions: `.jpg`, `.jpeg`, `.png`, `.webp`.
- Maximum image size: 20 MB per file.
- Reject empty image files.
- Reject production upload filenames that look like training, validation, or test dataset assets.
- Reject upload batches before processing when any file fails validation.
- Require `start_date` and `end_date` as ISO dates; `end_date` must be on or after `start_date`.
- Require an identified field/trap context before ingesting images.

## Normalization

- Trim leading/trailing spaces for all string values.
- Reject empty strings for required fields.
- Keep `field_id` and `trap_code` case-sensitive and immutable after ingest.

## Temporal consistency

- Reject capture timestamps in the future (with max tolerance 5 minutes).
- Reject malformed timezone values.

## Geospatial consistency

- If `gps` exists, both `lat` and `lon` are required.
- Coordinate bounds must be valid numeric ranges.

## Weather consistency

- Weather fields are optional.
- If provided, values must remain inside schema ranges.

## Error handling expectations

- Validation errors should return a clear field-level message.
- Unknown fields should be rejected to prevent schema drift.
