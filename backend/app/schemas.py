from pydantic import BaseModel, Field, field_validator
from typing import Optional
from uuid import UUID


class SearchFilters(BaseModel):
    category: Optional[str] = None
    price_max: Optional[int] = None
    price_min: Optional[int] = None
    availability: Optional[str] = None
    color: Optional[str] = None


class ScoreComponents(BaseModel):
    visual: float
    category_match: float
    color_match: float = 0.0
    popularity: float
    availability_boost: float
    business_boost: float


class SearchResultItem(BaseModel):
    product_id: UUID
    external_id: str
    title: Optional[str]
    url: Optional[str]
    image_url: Optional[str]
    price: Optional[int]
    currency: Optional[str]
    category: Optional[str]
    score: float
    score_components: ScoreComponents


class SearchResponse(BaseModel):
    request_id: UUID
    results: list[SearchResultItem]
    result_count: int
    confidence: str
    fallback_used: bool
    latency_ms: int


class ProductCreate(BaseModel):
    external_id: str
    title: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    price_cents: Optional[int] = None
    currency: Optional[str] = "INR"
    availability: Optional[str] = "in_stock"
    popularity_score: Optional[float] = None
    attributes: dict = Field(default_factory=dict)
    url: Optional[str] = None
    image_urls: list[str] = Field(default_factory=list)


class SyncJobResponse(BaseModel):
    job_id: UUID
    status: str
    stats: Optional[dict]


class HealthResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    status: str
    model_loaded: bool
    db: str
    redis: str
