from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ADMIN_PASSWORD = 'Admin123!ChangeMe'
PRODUCTION_ENVS = {'prod', 'production', 'staging'}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', case_sensitive=False)

    app_name: str = Field(default='SWD Monitoring API', alias='APP_NAME')
    app_env: str = Field(default='development', alias='APP_ENV')
    api_host: str = Field(default='0.0.0.0', alias='API_HOST')
    api_port: int = Field(default=8000, alias='API_PORT')

    secret_key: str = Field(alias='SECRET_KEY', min_length=32)
    access_token_expire_minutes: int = Field(default=120, ge=5, le=1440, alias='ACCESS_TOKEN_EXPIRE_MINUTES')

    postgres_url: str = Field(alias='POSTGRES_URL')

    neo4j_uri: str = Field(alias='NEO4J_URI')
    neo4j_user: str = Field(alias='NEO4J_USER')
    neo4j_password: str = Field(alias='NEO4J_PASSWORD')

    model_weights_path: str = Field(alias='MODEL_WEIGHTS_PATH')
    model_metrics_path: str = Field(default='../poc-model/model_metrics.json', alias='MODEL_METRICS_PATH')
    model_confidence: float = Field(default=0.25, alias='MODEL_CONFIDENCE')
    model_image_size: int = Field(default=640, alias='MODEL_IMAGE_SIZE')
    openai_api_key: str = Field(default='', alias='OPENAI_API_KEY')
    openai_chat_model: str = Field(default='gpt-4.1-mini', alias='OPENAI_CHAT_MODEL')

    upload_dir: str = Field(default='storage/uploads', alias='UPLOAD_DIR')
    cors_origins_raw: str = Field(default='http://localhost:5173', alias='CORS_ORIGINS')

    admin_email: str = Field(default='admin@local.test', alias='ADMIN_EMAIL')
    admin_password: str = Field(default=DEFAULT_ADMIN_PASSWORD, min_length=12, alias='ADMIN_PASSWORD')
    admin_name: str = Field(default='Local Admin', alias='ADMIN_NAME')

    @field_validator('app_env')
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode='after')
    def validate_security_settings(self) -> 'Settings':
        if self.app_env in PRODUCTION_ENVS:
            if self.admin_password == DEFAULT_ADMIN_PASSWORD:
                raise ValueError('ADMIN_PASSWORD must be changed outside local development')
            if '*' in self.cors_origins:
                raise ValueError('Wildcard CORS origins are not allowed outside local development')
        return self

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(',') if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
