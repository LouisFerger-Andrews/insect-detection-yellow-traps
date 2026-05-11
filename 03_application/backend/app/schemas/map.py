from typing import List

from pydantic import BaseModel, Field


class LatLng(BaseModel):
    lat: float
    lng: float


class TrapCreate(BaseModel):
    lat: float
    lng: float


class FieldMapCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    polygon: List[LatLng] = Field(min_length=3)
    traps: List[TrapCreate] = Field(default_factory=list)


class TrapResponse(BaseModel):
    id: str
    code: str
    name: str
    lat: float
    lng: float
    row_index: int
    position_index: int


class TrapUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class FieldMapSummary(BaseModel):
    id: str
    name: str
    area_m2: float
    trap_count: int


class FieldMapDetail(BaseModel):
    id: str
    name: str
    area_m2: float
    polygon: List[LatLng]
    traps: List[TrapResponse]


class SearchResult(BaseModel):
    display_name: str
    lat: float
    lng: float
