import os
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Lecture Note Q&A System"
    APP_VERSION: str = "1.0.0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    CHUNK_SIZE: int = 400
    CHUNK_OVERLAP: int = 50

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    FAISS_INDEX_PATH: str = "data/faiss_index"
    DOCUMENTS_PATH: str = "media/data_source"

    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS: set = {".pdf"}
    UPLOAD_INDEXING_STRATEGY: str = "full_rebuild"
    UPLOAD_INDEXING_ASYNC: bool = True

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    LLM_PROVIDER: str = "gemini"

    LOCAL_QWEN_MODEL: str = "qwen2.5:3b"
    LOCAL_QWEN_BASE_URL: str = "http://localhost:11434"
    LOCAL_QWEN_TIMEOUT_SECONDS: int = 300
    LOCAL_QWEN_KEEP_ALIVE: str = "30m"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"release", "prod", "production", "false", "0", "off"}:
                return False
            if lowered in {"debug", "dev", "development", "true", "1", "on"}:
                return True

        return value

    @field_validator("UPLOAD_INDEXING_STRATEGY", mode="before")
    @classmethod
    def validate_upload_indexing_strategy(cls, value):
        strategy = str(value).strip().lower()
        allowed = {"full_rebuild", "append"}
        if strategy not in allowed:
            return "full_rebuild"
        return strategy


def get_settings() -> Settings:
    settings = Settings()

    settings.FAISS_INDEX_PATH = str(Path(settings.FAISS_INDEX_PATH).resolve())
    settings.DOCUMENTS_PATH = str(Path(settings.DOCUMENTS_PATH).resolve())

    os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
    os.makedirs(settings.DOCUMENTS_PATH, exist_ok=True)

    return settings


settings = get_settings()
