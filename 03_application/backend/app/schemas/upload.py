from datetime import date, datetime
from typing import List

from pydantic import BaseModel


class DetectionResponse(BaseModel):
    class_id: int
    confidence: float
    bbox_xyxy: List[float]


class UploadResult(BaseModel):
    upload_id: int
    filename: str
    field_id: str
    trap_code: str
    capture_date: date
    detection_count: int
    confidence_avg: float
    detections: List[DetectionResponse]


class UploadBatchResponse(BaseModel):
    total_images: int
    start_date: date
    end_date: date
    results: List[UploadResult]


class UploadSummary(BaseModel):
    id: int
    user_id: int
    field_id: str
    trap_id: str | None = None
    trap_code: str
    capture_date: date
    image_path: str
    detection_count: int
    confidence_avg: float
    created_at: datetime

    model_config = {'from_attributes': True}


class UploadDetail(UploadSummary):
    detections: List[DetectionResponse]
