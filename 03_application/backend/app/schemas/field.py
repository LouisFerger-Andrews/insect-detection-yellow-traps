from pydantic import BaseModel, Field


class FieldCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    location: str = Field(default='Unknown', max_length=255)


class FieldResponse(BaseModel):
    id: str
    name: str
    location: str
    owner_user_id: int
