from uuid import uuid4

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.schemas.field import FieldCreateRequest, FieldResponse
from app.services.graph_service import GraphService

router = APIRouter(prefix='/api/fields', tags=['fields'])


@router.post('', response_model=FieldResponse)
def create_field(payload: FieldCreateRequest, current_user: User = Depends(get_current_user)):
    field_id = f'field-{uuid4().hex[:16]}'
    graph = GraphService()
    try:
        result = graph.create_field(current_user.id, field_id, payload.name, payload.location)
    finally:
        graph.close()
    return FieldResponse(**result)


@router.get('', response_model=list[FieldResponse])
def list_fields(current_user: User = Depends(get_current_user)):
    graph = GraphService()
    try:
        rows = graph.list_fields_for_user(current_user.id, is_admin=current_user.role == 'admin')
    finally:
        graph.close()
    return [FieldResponse(**row) for row in rows]
