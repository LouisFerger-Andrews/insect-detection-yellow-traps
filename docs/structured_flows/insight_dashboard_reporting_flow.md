# Insight Dashboard Reporting Flow

## Goal

Provide a V1 decision-support dashboard for reviewing insect detection results, monitoring activity trends, inspecting image-level predictions, and exporting report-ready data.

## Dashboard Inputs

The insight dashboard is backed by stored upload and detection records.

Filters:

- Field
- Trap code
- Start date
- End date
- Minimum detections
- Minimum average confidence

The API applies the current user's access scope. Admin users can review all fields; regular users only see uploads from fields they own.

## Dashboard Outputs

### KPIs

- Processed images
- Total detections
- Average detections per image
- Highest activity field
- Highest activity trap

### Trends and Comparisons

- Detection trend over time
- Field comparison by total detections
- Trap comparison by total detections
- Trap comparison by average detections per image

### Image-Level Table

The result table includes:

- Image reference
- Field
- Trap ID or field-level trap code
- Capture date
- Detection count
- Average confidence
- Stored prediction count

Users can open an image result to inspect stored prediction metadata, including class ID, confidence score, and bounding box coordinates.

## Export

CSV export is available from the dashboard.

The export includes:

- Dataset version
- Model version
- Access scope
- Selected filters
- Image-level result rows
- Prediction metadata per image

Endpoint:

```text
GET /api/analytics/insights/export.csv
```

The matching JSON endpoint for the dashboard is:

```text
GET /api/analytics/insights
```

## Repeatable Workflow

1. Open Monitoring Analytics.
2. Select a field or leave the field filter empty for all accessible fields.
3. Optionally enter trap code, date range, minimum detections, or confidence threshold.
4. Apply filters.
5. Review KPIs, trend charts, comparison charts, and image-level results.
6. Open individual image rows when prediction details are needed.
7. Export CSV for reporting or external analysis.

## Automated Coverage

- `03_application/tests/backend/test_analytics_environment_inference.py::test_insight_dashboard_filters_kpis_results_and_predictions`
  verifies filtered KPIs, trends, comparisons, image-level rows, detection metadata, and ownership scope.
- `03_application/tests/backend/test_analytics_environment_inference.py::test_insight_dashboard_csv_export_includes_context_and_rows`
  verifies CSV export includes context and report rows.
- `03_application/frontend/src/pages/__tests__/DashboardPage.test.tsx::renders insight dashboard filters, inspection, and export`
  verifies users can view dashboard results, apply filters, inspect an image result, and start CSV export.
