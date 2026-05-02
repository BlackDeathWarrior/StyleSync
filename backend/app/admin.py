"""Admin API routes — dashboard-facing endpoints for the pilot tenant."""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .models import (
    ApiKey, Embedding, Product, ProductImage, Search, SyncJob, Tenant, utcnow,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"])

PILOT_TENANT_ID = settings.pilot_tenant_id


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    status: str
    config: dict


class ApiKeyCreate(BaseModel):
    name: Optional[str] = None
    scopes: list[str] = ["search:read"]


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: Optional[str]
    key_prefix: str
    scopes: list[str]
    created_at: datetime
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]


class ApiKeyCreated(ApiKeyOut):
    full_key: str


class ProductOut(BaseModel):
    id: uuid.UUID
    external_id: str
    title: Optional[str]
    category: Optional[str]
    price_cents: Optional[int]
    availability: Optional[str]
    image_count: int
    embedded_count: int
    pending_count: int
    failed_count: int


class CatalogStats(BaseModel):
    total_products: int
    total_images: int
    embedded: int
    pending: int
    failed: int


class SyncJobOut(BaseModel):
    id: uuid.UUID
    source: str
    status: str
    stats: Optional[dict]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error: Optional[str]


class AnalyticsSummary(BaseModel):
    searches_today: int
    searches_7d: int
    avg_latency_ms: Optional[float]
    p95_latency_ms: Optional[int]
    no_result_rate: float
    low_confidence_rate: float
    top_categories: list[dict]


class RankingWeightsUpdate(BaseModel):
    w_visual: Optional[float] = None
    w_category: Optional[float] = None
    w_color: Optional[float] = None
    w_popularity: Optional[float] = None
    w_availability: Optional[float] = None
    w_boost: Optional[float] = None


@router.get("/tenant", response_model=TenantOut)
async def get_tenant(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.id == PILOT_TENANT_ID))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Pilot tenant not found")
    return TenantOut(
        id=tenant.id, name=tenant.name, slug=tenant.slug,
        plan=tenant.plan, status=tenant.status, config=tenant.config or {},
    )


@router.patch("/tenant/ranking-weights")
async def update_ranking_weights(body: RankingWeightsUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.id == PILOT_TENANT_ID))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Pilot tenant not found")
    config = dict(tenant.config or {})
    existing_weights = dict(config.get("ranking_weights", {}))
    existing_weights.update(body.model_dump(exclude_none=True))
    config["ranking_weights"] = existing_weights
    tenant.config = config
    await db.commit()
    return {"ranking_weights": existing_weights}


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ApiKey).where(ApiKey.tenant_id == PILOT_TENANT_ID).order_by(desc(ApiKey.created_at))
    )
    return [
        ApiKeyOut(id=k.id, name=k.name, key_prefix=k.key_prefix, scopes=k.scopes or [],
                  created_at=k.created_at, last_used_at=k.last_used_at, revoked_at=k.revoked_at)
        for k in result.scalars().all()
    ]


@router.post("/api-keys", response_model=ApiKeyCreated)
async def create_api_key(body: ApiKeyCreate, db: AsyncSession = Depends(get_db)):
    raw = secrets.token_urlsafe(32)
    prefix = raw[:8]
    full_key = f"sk_live_{prefix}_{raw}"
    key = ApiKey(
        tenant_id=PILOT_TENANT_ID,
        key_hash=hashlib.sha256(full_key.encode()).digest(),
        key_prefix=prefix, name=body.name, scopes=body.scopes,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return ApiKeyCreated(id=key.id, name=key.name, key_prefix=key.key_prefix, scopes=key.scopes or [],
                         created_at=key.created_at, last_used_at=key.last_used_at,
                         revoked_at=key.revoked_at, full_key=full_key)


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(key_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == PILOT_TENANT_ID)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.revoked_at = utcnow()
    await db.commit()


@router.get("/catalog/stats", response_model=CatalogStats)
async def catalog_stats(db: AsyncSession = Depends(get_db)):
    async def count(model, extra=None):
        conds = [model.tenant_id == PILOT_TENANT_ID]
        if extra is not None:
            conds.append(extra)
        return await db.scalar(select(func.count()).select_from(model).where(*conds)) or 0

    return CatalogStats(
        total_products=await count(Product),
        total_images=await count(ProductImage),
        embedded=await count(ProductImage, ProductImage.status == "embedded"),
        pending=await count(ProductImage, ProductImage.status == "pending"),
        failed=await count(ProductImage, ProductImage.status == "failed"),
    )


@router.get("/catalog/products", response_model=list[ProductOut])
async def list_products(
    limit: int = 50, offset: int = 0, category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    conditions = [Product.tenant_id == PILOT_TENANT_ID]
    if category:
        conditions.append(Product.category == category)
    products = (await db.execute(
        select(Product).where(*conditions).order_by(desc(Product.created_at)).limit(limit).offset(offset)
    )).scalars().all()

    result = []
    for p in products:
        async def cnt(s):
            return await db.scalar(
                select(func.count()).select_from(ProductImage).where(
                    ProductImage.product_id == p.id, ProductImage.status == s)
            ) or 0
        total = await db.scalar(
            select(func.count()).select_from(ProductImage).where(ProductImage.product_id == p.id)
        ) or 0
        result.append(ProductOut(
            id=p.id, external_id=p.external_id, title=p.title, category=p.category,
            price_cents=p.price_cents, availability=p.availability, image_count=total,
            embedded_count=await cnt("embedded"), pending_count=await cnt("pending"), failed_count=await cnt("failed"),
        ))
    return result


@router.get("/sync/jobs", response_model=list[SyncJobOut])
async def list_sync_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SyncJob).where(SyncJob.tenant_id == PILOT_TENANT_ID).order_by(desc(SyncJob.started_at)).limit(20)
    )
    return [
        SyncJobOut(id=j.id, source=j.source, status=j.status, stats=j.stats,
                   started_at=j.started_at, finished_at=j.finished_at, error=j.error)
        for j in result.scalars().all()
    ]


@router.post("/sync/trigger", response_model=SyncJobOut)
async def trigger_sync(db: AsyncSession = Depends(get_db)):
    job = SyncJob(tenant_id=PILOT_TENANT_ID, source="manual", status="queued", started_at=utcnow())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return SyncJobOut(id=job.id, source=job.source, status=job.status, stats=job.stats,
                      started_at=job.started_at, finished_at=job.finished_at, error=job.error)


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def analytics_summary(db: AsyncSession = Depends(get_db)):
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    searches_today = await db.scalar(
        select(func.count()).select_from(Search).where(
            Search.tenant_id == PILOT_TENANT_ID, Search.created_at >= today_start)
    ) or 0
    searches_7d = await db.scalar(
        select(func.count()).select_from(Search).where(
            Search.tenant_id == PILOT_TENANT_ID, Search.created_at >= week_ago)
    ) or 0
    avg_latency = await db.scalar(
        select(func.avg(Search.latency_ms)).where(
            Search.tenant_id == PILOT_TENANT_ID, Search.created_at >= week_ago)
    )

    p95_latency = None
    if searches_7d > 0:
        offset_n = max(0, int(searches_7d * 0.95) - 1)
        p95_val = (await db.execute(
            select(Search.latency_ms).where(
                Search.tenant_id == PILOT_TENANT_ID, Search.created_at >= week_ago
            ).order_by(Search.latency_ms).offset(offset_n).limit(1)
        )).scalar_one_or_none()
        p95_latency = p95_val

    no_result_count = await db.scalar(
        select(func.count()).select_from(Search).where(
            Search.tenant_id == PILOT_TENANT_ID, Search.created_at >= week_ago, Search.result_count == 0)
    ) or 0
    low_conf_count = await db.scalar(
        select(func.count()).select_from(Search).where(
            Search.tenant_id == PILOT_TENANT_ID, Search.created_at >= week_ago,
            Search.top1_score.isnot(None), Search.top1_score < 0.6)
    ) or 0

    return AnalyticsSummary(
        searches_today=searches_today, searches_7d=searches_7d,
        avg_latency_ms=float(avg_latency) if avg_latency else None,
        p95_latency_ms=p95_latency,
        no_result_rate=round((no_result_count / searches_7d) if searches_7d > 0 else 0.0, 4),
        low_confidence_rate=round((low_conf_count / searches_7d) if searches_7d > 0 else 0.0, 4),
        top_categories=[],
    )
