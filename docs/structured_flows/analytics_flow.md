# Analytics Flow

## Goal
Aggregate uploads/detections into user-facing monitoring metrics.

## Preconditions
- Upload and detection data exist in database.
- User has access to target field scope.

## Sequence
1. API receives analytics query (field/year/scope filters).
2. Query layer builds scoped SQL aggregations.
3. Totals and time-bucket metrics are computed.
4. Optional environmental context is joined where available.
5. Response payload is returned for dashboard rendering.

## Failure handling
- Invalid filters -> HTTP 400.
- Unauthorized field access -> HTTP 403.
- Data-source failure -> HTTP 500 with server logs.
