from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 200
    max_csv_rows: int = 50_000
    llm_provider: str = "none"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b-instruct"
    max_llm_chars: int = 20_000
    min_rows_threshold: int = 1
    llm_redact_local: bool = False

    model_config = SettingsConfigDict(env_prefix="statement_converter_")


settings = Settings()
