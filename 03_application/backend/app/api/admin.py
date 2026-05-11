from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models import Detection, TrapUpload, User

router = APIRouter(prefix='/api/admin', tags=['admin'])


@router.get('/overview')
def admin_overview(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    _ = admin_user
    users = db.query(User).order_by(User.created_at.desc()).all()
    uploads = db.query(TrapUpload).order_by(TrapUpload.created_at.desc()).limit(500).all()
    detections = db.query(Detection).count()

    return {
        'totals': {
            'users': len(users),
            'uploads': len(uploads),
            'detections': detections,
        },
        'users': [
            {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'created_at': user.created_at,
            }
            for user in users
        ],
        'uploads': [
            {
                'id': upload.id,
                'user_id': upload.user_id,
                'field_id': upload.field_id,
                'trap_id': upload.trap_id,
                'trap_code': upload.trap_code,
                'capture_date': upload.capture_date,
                'detection_count': upload.detection_count,
                'confidence_avg': upload.confidence_avg,
                'created_at': upload.created_at,
            }
            for upload in uploads
        ],
    }
