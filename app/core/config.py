from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/study_planner"
    EMBED_MODEL_NAME: str = "intfloat/multilingual-e5-small"
    APP_ENV: str = "dev"
    
    # Data directories
    DATA_DIR: str = "data"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
