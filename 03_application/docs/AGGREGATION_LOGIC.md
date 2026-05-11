# Aggregated and Time-Based Monitoring Views

## Overview

The monitoring analytics system provides aggregated detection insights across multiple dimensions: time, location (fields), and detection equipment (traps). This documentation describes the system architecture, data structures, and calculation methods for MVP-level operational monitoring of insect populations.

## System Architecture

### Key Components

1. **Backend API** (`/api/analytics/`)
   - `GET /insights` - Primary aggregated dashboard endpoint
   - `GET /insights/export.csv` - CSV export for reporting
   - `GET /overview` - Quick analytics overview

2. **Data Model**
   - **TrapUpload**: Individual image upload with detection results
   - **Detection**: Individual detected insect instances within images
   - **FieldMap**: Geographic field definitions and metadata
   - **User**: Access control for field ownership

### Database Schema

```
FieldMap
├── id (primary key)
├── name (field location identifier)
├── owner_user_id (access control)
├── polygon_geojson (geographic boundary)
└── area_m2 (field size)

TrapUpload
├── id (primary key)
├── field_id (references FieldMap)
├── trap_id (unique trap identifier)
├── trap_code (readable trap label, e.g., "T-A")
├── image_path (storage location)
├── capture_date (image acquisition timestamp)
├── detection_count (count of insects detected)
└── confidence_avg (average model confidence)

Detection
├── id (primary key)
├── upload_id (references TrapUpload)
├── class_id (insect species classification)
├── confidence (instance-level classification score)
├── x1, y1, x2, y2 (bounding box coordinates)
└── [additional detection metadata]
```

## Aggregation Dimensions

### 1. Time-Based Aggregation

**Daily Aggregation (Default)**
- Bucket: Calendar date (`capture_date`)
- Metrics per day:
  - `images`: Count of uploaded images
  - `detections`: Total insect detections across all images
  - `avg_detections_per_image`: Average insects per image (detections / images)

**Implementation**
```python
date_key = upload.capture_date.isoformat()  # e.g., "2026-05-15"
trend_bucket = trend_totals.setdefault(
    date_key,
    {'capture_date': date_key, 'images': 0, 'detections': 0}
)
trend_bucket['images'] += 1
trend_bucket['detections'] += upload.detection_count
```

### 2. Spatial Aggregation by Field

**Field-Level Rollup**
- Dimension: `field_id` (geographic location)
- Metrics per field:
  - `field_name`: Readable field label
  - `images`: Total uploads from this field
  - `detections`: Sum of all detected insects
  - `avg_detections_per_image`: Average insects per upload

**Use Case**: Compare activity across multiple fields in portfolio

### 3. Equipment Aggregation by Trap

**Trap Code Rollup**
- Dimension: `trap_code` (individual sticky trap identifier)
- Metrics per trap:
  - `trap_code`: Human-readable trap label (e.g., "T-A", "R01-P01")
  - `images`: Count of images captured on this trap
  - `detections`: Sum of detections from this trap
  - `avg_detections_per_image`: Detection rate per image

**Use Case**: Identify high-activity traps for field scouting prioritization

## Filtering Pipeline

### Query Filters

All filters operate as conjunctions (AND logic) applied to the base query:

| Filter | Type | Description |
|--------|------|-------------|
| `field_id` | String | Restrict to single field UUID |
| `trap_id` | String | Restrict to specific stored trap UUID/identifier |
| `trap_code` | String | Restrict to specific trap identifier |
| `start_date` | Date | Include uploads >= this date |
| `end_date` | Date | Include uploads <= this date |
| `min_detections` | Integer | Include uploads with >= detections |
| `max_detections` | Integer | Include uploads with <= detections |
| `min_confidence` | Float [0.0, 1.0] | Include if avg_confidence >= threshold |

### Validation Rules

- `start_date` must be ≤ `end_date` (if both provided)
- `min_detections` must be ≤ `max_detections` (if both provided)
- `min_confidence` must be in range [0.0, 1.0]
- Non-admin users only see fields they own

### Example Filter Scenario

```
GET /api/analytics/insights?
  field_id=north-field-2026
  &start_date=2026-05-01
  &end_date=2026-05-31
  &min_detections=2
  &max_detections=20
  &min_confidence=0.6
```

Result: Images from North Field in May with 2-20 high-confidence detections

## Aggregation Output Structure

### Response Format

```json
{
  "context": {
    "scope": "owned-fields|all-fields",
    "dataset_version": "metadata-v1.0.0",
    "model_version": "model-weights-filename.pt",
    "filters": {
      "field_id": "...",
      "trap_id": "...",
      "trap_code": "...",
      "start_date": "2026-05-01",
      "end_date": "2026-05-31",
      "min_detections": 2,
      "max_detections": 20,
      "min_confidence": 0.6
    }
  },
  "kpis": {
    "processed_images": 485,
    "total_detections": 3421,
    "avg_detections_per_image": 7.052,
    "highest_activity_field": {
      "field_id": "north-field",
      "field_name": "North Field",
      "images": 250,
      "detections": 1850,
      "avg_detections_per_image": 7.4
    },
    "highest_activity_trap": {
      "trap_code": "T-A",
      "images": 50,
      "detections": 425,
      "avg_detections_per_image": 8.5
    }
  },
  "trend": [
    {
      "capture_date": "2026-05-01",
      "images": 15,
      "detections": 105,
      "avg_detections_per_image": 7.0
    },
    ...
  ],
  "comparisons": {
    "by_field": [
      {
        "field_id": "north-field",
        "field_name": "North Field",
        "images": 250,
        "detections": 1850,
        "avg_detections_per_image": 7.4
      },
      ...
    ],
    "by_trap": [
      {
        "trap_code": "T-A",
        "images": 50,
        "detections": 425,
        "avg_detections_per_image": 8.5
      },
      ...
    ]
  },
  "results": [
    {
      "upload_id": 12345,
      "image_path": "storage/uploads/field-xxx/2026/05/15/T-A/image.jpg",
      "field_id": "north-field",
      "field_name": "North Field",
      "trap_id": "trap-001",
      "trap_code": "T-A",
      "capture_date": "2026-05-15",
      "detection_count": 8,
      "confidence_avg": 0.723,
      "detections": [
        {
          "class_id": 0,
          "confidence": 0.91,
          "bbox_xyxy": [100.5, 200.3, 150.8, 250.2]
        },
        ...
      ]
    },
    ...
  ]
}
```

## KPI Definitions

### Core Metrics

| KPI | Calculation | Interpretation |
|-----|-----------|-----------------|
| **Processed Images** | Count of uploads matching filters | Data volume in analysis |
| **Total Detections** | Sum of `detection_count` across uploads | Overall pest pressure |
| **Avg/Image** | Total Detections / Processed Images | Detection intensity per observation |
| **Highest Field** | Field with max detections | Primary activity location |
| **Highest Trap** | Trap with max detections | Most active monitoring point |

### Derived Metrics

**Trap Activity Rate**
- Definition: `detections / images` for a trap
- Use: Identify traps with consistently high activity

**Field Comparison Index**
- Rank fields by detection totals
- Use: Resource allocation and monitoring priority

**Temporal Trend**
- Daily detection counts over time
- Use: Track population dynamics and intervention timing

## Data Quality Handling

### Missing Metadata

**Scenario**: Upload lacks trap association
- Action: Include in aggregations but flag trap_id as null
- Display: Show as "Unassigned" in trap comparisons
- Impact: Still counted in daily and field aggregations

**Scenario**: Upload has no field metadata
- Action: Cannot include (foreign key violation would prevent storage)
- Prevention: Enforce field_id at upload validation

**Scenario**: Detection recording fails for an upload
- Action: Use `detection_count` from TrapUpload (pre-computed)
- Fallback: System calculates from raw Detection records if needed
- Traceability: Results remain linkable to source images

### Confidence Filtering

- Model provides per-detection confidence scores
- TrapUpload stores pre- computed average (`confidence_avg`)
- Filter applied at query time on TrapUpload.confidence_avg
- Threshold: Typical range 0.6-0.8 for operational filtering

## Traceability Design

### Image-Level Drill-Down

1. User sees aggregated KPI: "North Field: 250 images, 1850 detections"
2. User clicks chart bar → Filtered results table loads
3. Table rows show individual uploads with full metadata
4. User clicks row → Detail view of specific image and all detections
5. Detail shows bounding boxes and individual detection scores

### Audit Trail

- Context always includes applied filters
- CSV export prefixes metadata with execution parameters
- Results sorted consistently (date DESC, then ID DESC)
- Reproducibility: Same filter query returns same results

## Performance Considerations

### Query Limits

- Default limit: 500 most recent uploads per query
- Rationale: Balance responsiveness with completeness
- CSV export: No limit (exports all matching records)

### Indexing Strategy

- Primary index: `(field_id, capture_date DESC)`
- Secondary: `(trap_code, capture_date DESC)`
- Filtering: Dates significantly reduce scan scope

### Aggregation Computation

- All aggregations computed in-memory after query
- No materialized summary tables (supports real-time filtering)
- Scaling: Suitable for up to ~100k uploads; consider materialization beyond

## API Documentation

### GET /api/analytics/insights

Returns aggregated detections with KPIs and detailed results.

**Parameters**
```
field_id: string (optional) - Filter to field
trap_id: string (optional) - Filter to stored trap identifier
trap_code: string (optional) - Filter to trap
start_date: date (optional) - YYYY-MM-DD
end_date: date (optional) - YYYY-MM-DD
min_detections: integer (optional, >= 0)
max_detections: integer (optional, >= 0)
min_confidence: float (optional, 0.0-1.0)
```

**Response**: See output format above

### GET /api/analytics/insights/export.csv

Exports detailed results as CSV with context metadata.

**CSV Structure**:
- Header rows: Dataset version, model, filters
- Data rows: One per upload with full detection metadata

### GET /api/analytics/overview

Quick summary without image-level details. Suitable for dashboards.

**Parameters**:
```
field_id: string (optional)
year: integer (optional, 2000-2100)
```

**Response**: Simplified with only aggregates (no results array)

## Usage Examples

### Example 1: Monitor Weekly Trap Activity
```
GET /insights?
  trap_code=T-A
  &start_date=2026-05-08
  &end_date=2026-05-14
```
Result: 7-day detection trend for trap T-A

### Example 2: Quality Control with Confidence Filter
```
GET /insights?
  field_id=north-field
  &min_confidence=0.75
```
Result: Only high-confidence detections for North Field validates model performance

### Example 3: Anomaly Detection
```
GET /insights?
  min_detections=50
```
Result: Images with unusually high detections (potential data recording errors or pest outbreaks)

### Example 4: Export Weekly Report
```
GET /insights/export.csv?
  field_id=north-field
  &start_date=2026-05-01
  &end_date=2026-05-07
```
Result: CSV ready for email or dashboard integration

## Version History

- **v1.0.0** (2026-05-11): Initial release
  - Daily time-based aggregation
  - Field and trap spatial aggregation
  - Filtering by date, detection count, confidence
  - CSV export capability
  - Full detection-level traceability

## Future Enhancements

- Weekly/monthly aggregation options (configurable time buckets)
- Geographic heatmaps (GeoJSON output)
- Species-level aggregation (by detection class_id)
- Predictive trend analysis
- Automated alert thresholds
- Historical baseline comparisons
