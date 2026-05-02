import time
import uuid
import logging
from typing import Optional

import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import Embedding, Product, ProductImage, Search, Tenant
from .schemas import ScoreComponents, SearchFilters, SearchResultItem, SearchResponse

logger = logging.getLogger(__name__)


def _compute_confidence(results: list[dict]) -> str:
    if not results:
        return "low"
    top1 = results[0]["cosine"]
    if top1 >= 0.8:
        return "high"
    if top1 >= 0.6:
        return "medium"
    return "low"


def _color_sim(product_attrs: dict, filter_color: Optional[str]) -> float:
    if not filter_color:
        return 0.0
    product_color = (product_attrs or {}).get("color", "")
    if not product_color:
        return 0.0
    return 1.0 if filter_color.lower() in product_color.lower() else 0.0


def _rank(
    rows: list[dict],
    filters: SearchFilters,
    weights: dict,
) -> list[dict]:
    w_v = weights.get("w_visual", settings.w_visual)
    w_c = weights.get("w_category", settings.w_category)
    w_col = weights.get("w_color", settings.w_color)
    w_p = weights.get("w_popularity", settings.w_popularity)
    w_a = weights.get("w_availability", settings.w_availability)
    w_b = weights.get("w_boost", settings.w_boost)

    pops = [r["popularity_score"] or 0.0 for r in rows]
    max_pop = max(pops, default=1.0) or 1.0

    scored = []
    for r in rows:
        cosine = r["cosine"]
        category_match = 1.0 if (filters.category and r["category"] == filters.category) else 0.0
        color_sim = _color_sim(r.get("attributes") or {}, filters.color)
        avail_boost = 1.0 if r["availability"] == "in_stock" else 0.0
        pop_norm = (r["popularity_score"] or 0.0) / max_pop
        business_boost = 0.0

        score = (
            w_v * cosine
            + w_c * category_match
            + w_col * color_sim
            + w_p * pop_norm
            + w_a * avail_boost
            + w_b * business_boost
        )

        r["score"] = score
        r["score_components"] = ScoreComponents(
            visual=round(cosine, 4),
            category_match=round(category_match, 4),
            color_match=round(color_sim, 4),
            popularity=round(pop_norm, 4),
            availability_boost=round(avail_boost, 4),
            business_boost=round(business_boost, 4),
        )
        scored.append(r)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


async def visual_search(
    db: AsyncSession,
    query_embedding: np.ndarray,
    query_hash: bytes,
    tenant_id: uuid.UUID,
    filters: SearchFilters,
    limit: int = settings.search_default_limit,
    top_k: int = settings.search_top_k,
    session_id: Optional[str] = None,
) -> SearchResponse:
    t0 = time.perf_counter()
    request_id = uuid.uuid4()

    query_vec = query_embedding.tolist()

    conditions = [
        Embedding.tenant_id == tenant_id,
        Product.tenant_id == tenant_id,
    ]
    if filters.availability:
        conditions.append(Product.availability == filters.availability)
    if filters.price_max is not None:
        conditions.append(Product.price_cents <= filters.price_max * 100)
    if filters.price_min is not None:
        conditions.append(Product.price_cents >= filters.price_min * 100)
    if filters.category:
        conditions.append(Product.category == filters.category)

    stmt = (
        select(
            Embedding.id.label("embedding_id"),
            Embedding.product_id,
            (1 - Embedding.embedding.cosine_distance(query_vec)).label("cosine"),
            Product.external_id,
            Product.title,
            Product.url,
            Product.price_cents,
            Product.currency,
            Product.category,
            Product.availability,
            Product.popularity_score,
            Product.attributes,
            ProductImage.source_url.label("image_url"),
        )
        .join(Product, Embedding.product_id == Product.id)
        .join(ProductImage, Embedding.product_image_id == ProductImage.id)
        .where(and_(*conditions))
        .order_by(Embedding.embedding.cosine_distance(query_vec))
        .limit(top_k)
    )

    result = await db.execute(stmt)
    rows = [dict(r._mapping) for r in result.fetchall()]

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    tenant_config = (tenant.config or {}).get("ranking_weights", {}) if tenant else {}
    ranked = _rank(rows, filters, tenant_config)
    page = ranked[:limit]

    confidence = _compute_confidence(ranked)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    try:
        search_log = Search(
            tenant_id=tenant_id,
            query_image_hash=query_hash,
            filters=filters.model_dump(exclude_none=True),
            result_count=len(page),
            top1_score=page[0]["score"] if page else None,
            top1_product_id=page[0]["product_id"] if page else None,
            latency_ms=latency_ms,
            user_session_id=session_id,
        )
        db.add(search_log)
        await db.commit()
    except Exception:
        logger.warning("Failed to log search", exc_info=True)

    results = [
        SearchResultItem(
            product_id=r["product_id"],
            external_id=r["external_id"],
            title=r["title"],
            url=r["url"],
            image_url=r["image_url"],
            price=r["price_cents"],
            currency=r["currency"],
            category=r["category"],
            score=round(r["score"], 4),
            score_components=r["score_components"],
        )
        for r in page
    ]

    return SearchResponse(
        request_id=request_id,
        results=results,
        result_count=len(results),
        confidence=confidence,
        fallback_used=False,
        latency_ms=latency_ms,
    )
