# Metadata Specification

This folder defines the required metadata structure for insect yellow-trap uploads.

## Scope

- Canonical metadata fields
- Validation and formatting rules
- Example payloads for ingestion and API use

## Structure

- `schema/metadata.schema.json`: JSON Schema (source of truth)
- `rules/validation-rules.md`: practical validation rules and constraints
- `rules/collection-input-standards.md`: upload-time image and metadata standards
- `examples/`: minimal valid payload examples

## Versioning

Current version: `v1.0.0`

Any backward-incompatible change must bump major version and include migration notes.
