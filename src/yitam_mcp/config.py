"""Configuration, read from the environment (and an optional .env file).

Environment variable names are kept identical to the original TypeScript server so
an existing .env can be copied across unchanged.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Transport = Literal["stdio", "http", "sse"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Transport
    transport: Transport = "stdio"
    host: str = "127.0.0.1"
    port: int = 3000
    # Shared bearer token for HTTP/SSE. None/empty disables auth.
    mcp_auth_token: str | None = None

    # Qdrant
    collection_name: str = "vito"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # Gemini embeddings
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-embedding-001"
    # None means "use the model default" (3072 for gemini-embedding-001).
    gemini_embedding_dimensions: int | None = None

    # Search defaults
    default_limit: int = 10
    min_score_threshold: float = 0.7
    max_results: int = 20

    log_level: str = "INFO"


settings = Settings()
