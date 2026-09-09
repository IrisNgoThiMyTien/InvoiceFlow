from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ocr_provider: str = "mock"
    upload_dir: str = "uploads"
    db_path: str = "data/invoiceflow.db"
    max_upload_size_mb: int = 10

    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.6-27b"
    ocr_confidence_threshold: float = 0.4
    ocr_timeout_seconds: float = 30.0
    ocr_max_retries: int = 2

    @property
    def upload_dir_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def db_path_path(self) -> Path:
        return Path(self.db_path)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
