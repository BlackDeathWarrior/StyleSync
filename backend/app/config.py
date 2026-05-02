from pydantic_settings import BaseSettings, SettingsConfigDict
from uuid import UUID


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=("settings_",))

    database_url: str = "postgresql+asyncpg://stylesync:stylesync@localhost:5432/stylesync"
    redis_url: str = "redis://localhost:6379/0"
    env: str = "development"
    sentry_dsn: str = ""
    model_id: str = "patrickjohncyh/fashion-clip"
    pilot_tenant_id: UUID = UUID("00000000-0000-0000-0000-000000000001")

    # Ranking weights (defaults; overridable per tenant via config JSONB)
    w_visual: float = 0.65
    w_category: float = 0.15
    w_color: float = 0.05
    w_popularity: float = 0.05
    w_availability: float = 0.05
    w_boost: float = 0.05

    # Search defaults
    search_top_k: int = 200
    search_default_limit: int = 24
    embedding_cache_ttl: int = 86400  # 24 h


settings = Settings()
