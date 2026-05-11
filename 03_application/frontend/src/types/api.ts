export type UserProfile = {
  id: number;
  email: string;
  full_name: string;
  role: 'admin' | 'user';
};

export type Field = {
  id: string;
  name: string;
  location: string;
  owner_user_id: number;
};

export type LatLng = {
  lat: number;
  lng: number;
};

export type TrapPoint = {
  id: string;
  code: string;
  name: string;
  lat: number;
  lng: number;
  row_index: number;
  position_index: number;
};

export type FieldMapSummary = {
  id: string;
  name: string;
  area_m2: number;
  trap_count: number;
};

export type FieldMapDetail = {
  id: string;
  name: string;
  area_m2: number;
  polygon: LatLng[];
  traps: TrapPoint[];
};

export type SearchResult = {
  display_name: string;
  lat: number;
  lng: number;
};

export type Detection = {
  class_id: number;
  confidence: number;
  bbox_xyxy: number[];
};

export type UploadResult = {
  upload_id: number;
  filename: string;
  field_id: string;
  trap_code: string;
  capture_date: string;
  detection_count: number;
  confidence_avg: number;
  detections: Detection[];
};

export type UploadBatchResponse = {
  total_images: number;
  start_date: string;
  end_date: string;
  results: UploadResult[];
};

export type UploadSummary = {
  id: number;
  user_id: number;
  field_id: string;
  trap_id?: string | null;
  trap_code: string;
  capture_date: string;
  image_path: string;
  detection_count: number;
  confidence_avg: number;
  created_at: string;
};

export type UploadDetail = UploadSummary & {
  detections: Detection[];
};

export type AnalyticsOverview = {
  scope: 'all-fields' | 'owned-fields';
  selected_field_id?: string | null;
  selected_year?: number | null;
  available_years?: number[];
  totals: {
    uploads: number;
    detections: number;
    avg_detection_per_upload: number;
  };
  daily: Array<{
    capture_date: string;
    uploads: number;
    detections: number;
  }>;
  by_field: Array<{
    field_id: string;
    field_name: string;
    uploads: number;
    detections: number;
  }>;
  by_trap: Array<{
    trap_code: string;
    uploads: number;
    detections: number;
  }>;
};

export type ModelStats = {
  model: {
    weights_file: string;
    weights_path: string;
    confidence_threshold: number;
    image_size: number;
  };
  evaluation: {
    precision?: number;
    recall?: number;
    map50?: number;
    map50_95?: number;
    notes: string;
  };
  production_observed: {
    total_uploads: number;
    total_detections: number;
    average_upload_confidence: number;
  };
};

export type ExploratoryChatResponse = {
  answer: string;
  used_openai: boolean;
  provider_error: string;
  context: {
    totals: {
      uploads: number;
      detections: number;
      avg_confidence: number;
    };
    top_fields: Array<{
      field_id: string;
      uploads: number;
      detections: number;
    }>;
    top_traps: Array<{
      trap_code: string;
      uploads: number;
      detections: number;
    }>;
  };
};

export type ExploratoryReportResponse = ExploratoryChatResponse & {
  filename: string;
  html: string;
};

export type EnvironmentOverview = {
  selected_year?: number | null;
  available_years?: number[];
  fields: Array<{
    field_id: string;
    field_name: string;
    records: number;
    start_date: string | null;
    end_date: string | null;
    last_fetch_at: string | null;
    sources: Record<string, number>;
    latest: {
      date: string;
      temperature_mean_c: number | null;
      precipitation_mm: number | null;
      gdd_base10_c: number | null;
      water_deficit_mm: number | null;
    } | null;
  }>;
};

export type FieldTimeseries = {
  field_id: string;
  field_name: string;
  weeks: number;
  selected_year?: number | null;
  all_data?: boolean;
  start_date: string;
  end_date: string;
  population_weekly: Array<{
    week_start: string;
    uploads: number;
    avg_population: number;
    total_population: number;
  }>;
  weather_weekly: Array<{
    week_start: string;
    temp_avg: number;
    rain_sum: number;
    gdd_avg: number;
    deficit_avg: number;
    heat_stress_avg: number;
  }>;
  trap_weekly: Array<{
    week_start: string;
    trap_code: string;
    uploads: number;
    avg_population: number;
    total_population: number;
  }>;
};

export type InsightDashboard = {
  context: {
    scope: 'all-fields' | 'owned-fields';
    dataset_version: string;
    model_version: string;
    filters: {
      field_id?: string | null;
      trap_code?: string | null;
      start_date?: string | null;
      end_date?: string | null;
      min_detections?: number | null;
      min_confidence?: number | null;
    };
  };
  kpis: {
    processed_images: number;
    total_detections: number;
    avg_detections_per_image: number;
    highest_activity_field: null | {
      field_id: string;
      field_name: string;
      images: number;
      detections: number;
      avg_detections_per_image: number;
    };
    highest_activity_trap: null | {
      trap_code: string;
      images: number;
      detections: number;
      avg_detections_per_image: number;
    };
  };
  trend: Array<{
    capture_date: string;
    images: number;
    detections: number;
    avg_detections_per_image: number;
  }>;
  comparisons: {
    by_field: Array<{
      field_id: string;
      field_name: string;
      images: number;
      detections: number;
      avg_detections_per_image: number;
    }>;
    by_trap: Array<{
      trap_code: string;
      images: number;
      detections: number;
      avg_detections_per_image: number;
    }>;
  };
  results: Array<{
    upload_id: number;
    image_path: string;
    field_id: string;
    field_name: string;
    trap_id?: string | null;
    trap_code: string;
    capture_date: string;
    detection_count: number;
    confidence_avg: number;
    detections: Detection[];
  }>;
};
