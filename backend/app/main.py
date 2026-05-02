import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Optional

import redis.asyncio as aioredis
import xxhash
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .admin import router as admin_router
from .auth import set_redis as auth_set_redis
from .config import settings
from .database import get_db
from .embeddings import get_embedder
from .schemas import HealthResponse, ProductCreate, SearchFilters, SearchResponse
from .search import visual_search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis
    logger.info("Warming FashionCLIP model...")
    get_embedder()
    _redis = aioredis.from_url(settings.redis_url, decode_responses=False)
    auth_set_redis(_redis)
    logger.info("Redis connected")
    yield
    await _redis.aclose()


app = FastAPI(
    title="StyleSync API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)

PILOT_TENANT_ID = settings.pilot_tenant_id


@app.get("/health", response_model=HealthResponse, tags=["infra"])
async def health(db: AsyncSession = Depends(get_db)):
    db_ok = "ok"
    redis_ok = "ok"
    try:
        await db.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception as e:
        db_ok = str(e)
    try:
        await _redis.ping()
    except Exception as e:
        redis_ok = str(e)

    return HealthResponse(
        status="ok" if db_ok == "ok" and redis_ok == "ok" else "degraded",
        model_loaded=True,
        db=db_ok,
        redis=redis_ok,
    )


@app.get("/ready", tags=["infra"])
async def ready():
    return {"status": "ready"}


@app.post("/v1/search/visual", response_model=SearchResponse, tags=["search"])
async def search_visual(
    image: UploadFile = File(...),
    category: Optional[str] = Form(None),
    price_max: Optional[int] = Form(None),
    price_min: Optional[int] = Form(None),
    availability: Optional[str] = Form(None),
    limit: int = Form(settings.search_default_limit),
    session_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image format. Use JPEG, PNG, or WebP.")

    raw = await image.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Max 10 MB.")

    image_hash = xxhash.xxh64(raw).hexdigest()
    cache_key = f"stylesync:{PILOT_TENANT_ID}:emb:{image_hash}"

    embedder = get_embedder()

    cached = await _redis.get(cache_key) if _redis else None
    if cached:
        import numpy as np
        query_embedding = np.frombuffer(cached, dtype=np.float32)
        content_hash = xxhash.xxh64(raw).digest()
    else:
        query_embedding, content_hash = embedder.embed_bytes(raw)
        if _redis:
            await _redis.setex(cache_key, settings.embedding_cache_ttl, query_embedding.tobytes())

    filters = SearchFilters(
        category=category,
        price_max=price_max,
        price_min=price_min,
        availability=availability,
    )

    return await visual_search(
        db=db,
        query_embedding=query_embedding,
        query_hash=content_hash,
        tenant_id=PILOT_TENANT_ID,
        filters=filters,
        limit=min(limit, 100),
        session_id=session_id,
    )


@app.post("/v1/catalog/products", tags=["catalog"])
async def create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_db),
):
    from .models import Product as ProductModel, ProductImage as ProductImageModel
    import httpx

    p = ProductModel(
        tenant_id=PILOT_TENANT_ID,
        external_id=product.external_id,
        title=product.title,
        brand=product.brand,
        category=product.category,
        subcategory=product.subcategory,
        price_cents=product.price_cents,
        currency=product.currency,
        availability=product.availability,
        popularity_score=product.popularity_score,
        attributes=product.attributes,
        url=product.url,
    )
    db.add(p)
    await db.flush()

    for img_url in product.image_urls[:3]:
        pi = ProductImageModel(
            tenant_id=PILOT_TENANT_ID,
            product_id=p.id,
            source_url=img_url,
            status="pending",
        )
        db.add(pi)

    await db.commit()
    await db.refresh(p)
    return {"product_id": str(p.id), "external_id": p.external_id}


@app.post("/v1/catalog/embed/{product_image_id}", tags=["catalog"])
async def embed_product_image(
    product_image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Embed a single product image synchronously (PoC — no queue)."""
    from sqlalchemy import select
    from .models import ProductImage as ProductImageModel, Embedding as EmbeddingModel
    import httpx

    result = await db.execute(
        select(ProductImageModel).where(
            ProductImageModel.id == product_image_id,
            ProductImageModel.tenant_id == PILOT_TENANT_ID,
        )
    )
    pi = result.scalar_one_or_none()
    if not pi:
        raise HTTPException(status_code=404, detail="Product image not found")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(pi.source_url, follow_redirects=True)
            resp.raise_for_status()
            raw = resp.content
    except Exception as e:
        pi.status = "failed"
        pi.failure_reason = f"download_failed: {e}"
        await db.commit()
        raise HTTPException(status_code=422, detail=str(e))

    embedder = get_embedder()
    try:
        embedding, content_hash = embedder.embed_bytes(raw)
    except Exception as e:
        pi.status = "failed"
        pi.failure_reason = f"embed_failed: {e}"
        await db.commit()
        raise HTTPException(status_code=422, detail=str(e))

    pi.content_hash = content_hash
    pi.status = "embedded"

    emb = EmbeddingModel(
        tenant_id=PILOT_TENANT_ID,
        product_id=pi.product_id,
        product_image_id=pi.id,
        model_id=settings.model_id,
        embedding=embedding.tolist(),
    )
    db.add(emb)
    await db.commit()
    return {"status": "embedded", "product_image_id": str(pi.id)}
