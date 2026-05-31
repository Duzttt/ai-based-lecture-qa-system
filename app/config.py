import os
from pathlib import Path
from typing import Optional, Set

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Lecture Note Q&A System"
    APP_VERSION: str = "1.0.0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    FAISS_INDEX_PATH: str = "data/faiss_index"
    DOCUMENTS_PATH: str = "media/data_source"

    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS: str = ".pdf"
    UPLOAD_INDEXING_STRATEGY: str = "full_rebuild"
    UPLOAD_INDEXING_ASYNC: bool = True
    PDF_PARSER: str = "pypdf"  # "pypdf" or "opendataloader"

    @field_validator("PDF_PARSER", mode="before")
    @classmethod
    def validate_pdf_parser(cls, value):
        parser = str(value).strip().lower()
        if parser not in {"pypdf", "opendataloader"}:
            return "pypdf"
        return parser

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    LLM_PROVIDER: str = "gemini"
    LLM_MAX_OUTPUT_TOKENS: int = 2048
    CITATION_MAX_OUTPUT_TOKENS: int = 3072

    LOCAL_LLM_MODEL: str = "qwen2.5:3b"
    LOCAL_LLM_BASE_URL: str = "http://localhost:8080"
    LOCAL_LLM_TIMEOUT_SECONDS: int = 300

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

    @property
    def allowed_extensions(self) -> Set[str]:
        raw_value = str(self.ALLOWED_EXTENSIONS or "")
        parts = [part.strip().lower() for part in raw_value.split(",") if part.strip()]
        normalized = set()
        for ext in parts:
            normalized.add(ext if ext.startswith(".") else f".{ext}")
        return normalized or {".pdf"}

    @field_validator("GEMINI_API_KEY", "OPENROUTER_API_KEY", mode="before")
    @classmethod
    def normalize_optional_api_keys(cls, value):
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized or normalized.lower() in {"none", "null"}:
            return None
        return normalized


def get_settings() -> Settings:
    settings = Settings()

    settings.FAISS_INDEX_PATH = str(Path(settings.FAISS_INDEX_PATH).resolve())
    settings.DOCUMENTS_PATH = str(Path(settings.DOCUMENTS_PATH).resolve())

    os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
    os.makedirs(settings.DOCUMENTS_PATH, exist_ok=True)

    return settings


settings = get_settings()
