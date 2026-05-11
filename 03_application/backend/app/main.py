from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import admin, analysis, analytics, auth, environment, fields, map
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import engine
from app.models import User
from app.services.graph_service import GraphService

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth.router)
app.include_router(fields.router)
app.include_router(map.router)
app.include_router(analysis.router)
app.include_router(analytics.router)
app.include_router(environment.router)
app.include_router(admin.router)


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.on_event('startup')
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    _run_schema_upgrades()

    with Session(engine) as db:
        admin_user = db.query(User).filter(User.email == settings.admin_email.lower()).first()
        if admin_user is None:
            admin_user = User(
                email=settings.admin_email.lower(),
                full_name=settings.admin_name,
                password_hash=hash_password(settings.admin_password),
                role='admin',
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        graph_service = GraphService()
        try:
            graph_service.initialize()
            graph_service.ensure_user_node(admin_user.id, admin_user.email, admin_user.full_name)
            graph_service.seed_example_field(admin_user.id)
        finally:
            graph_service.close()


def _run_schema_upgrades() -> None:
    with Session(engine) as db:
        db.execute(text('ALTER TABLE trap_uploads ADD COLUMN IF NOT EXISTS trap_id VARCHAR(64)'))
        db.execute(text('ALTER TABLE trap_points ADD COLUMN IF NOT EXISTS custom_name VARCHAR(120)'))
        db.commit()
