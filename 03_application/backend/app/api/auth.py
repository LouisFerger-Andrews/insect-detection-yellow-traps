from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import check_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserProfile
from app.services.graph_service import GraphService

router = APIRouter(prefix='/api/auth', tags=['auth'])


@router.post('/register', response_model=UserProfile)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(request, scope='register', identifier=payload.email)
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email already in use')

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role='user',
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    graph_service = GraphService()
    try:
        graph_service.ensure_user_node(user.id, user.email, user.full_name)
    finally:
        graph_service.close()

    return user


@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(request, scope='login', identifier=payload.email)
    user = db.query(User).filter(User.email == payload.email.lower(), User.is_active.is_(True)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')

    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token)


@router.get('/me', response_model=UserProfile)
def me(current_user: User = Depends(get_current_user)):
    return current_user
