from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    news_api_key: str = ""
    news_api_keys: str = ""
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "news_pipeline"
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_graph: str = "worldgraph"
    groq_api_keys: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: str = "openai/gpt-oss-20b"
    groq_requests_per_minute: int = 8
    temporal_window_days: int = 3
    temporal_similarity_threshold: float = 0.70
    date_from: str = "2026-09-08"
    date_to: str = "2026-10-07"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 64
    dbscan_eps: float = 0.35
    dbscan_min_samples: int = 2
    simhash_distance_threshold: int = 1
    default_query: str = "*"
    default_language: str = "en"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_api_keys(self) -> list[str]:
        keys = []
        if self.news_api_keys:
            for k in self.news_api_keys.split(","):
                cleaned = k.strip()
                if cleaned and cleaned not in keys:
                    keys.append(cleaned)
        if self.news_api_key:
            cleaned = self.news_api_key.strip()
            if cleaned and cleaned not in keys:
                keys.append(cleaned)
        return keys

    def get_groq_api_keys(self) -> list[str]:
        keys = []
        if self.groq_api_keys:
            for k in self.groq_api_keys.split(","):
                cleaned = k.strip()
                if cleaned and cleaned not in keys:
                    keys.append(cleaned)
        return keys


@lru_cache()
def get_settings() -> Settings:
    return Settings()

