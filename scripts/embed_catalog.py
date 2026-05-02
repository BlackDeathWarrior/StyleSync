#!/usr/bin/env python3
"""
Bulk catalog ingestion script for the PoC.

Usage:
    python scripts/embed_catalog.py --csv data/catalog.csv --batch-size 64

CSV format (header required):
    external_id,title,category,price,currency,availability,url,image_url,brand,color

Reads each row, downloads the image, embeds it via FashionCLIP, and upserts into Postgres.
Idempotent: skips images whose content_hash already exists in the DB.
"""

import argparse
import asyncio
import csv
import io
import logging
import sys
import uuid
from pathlib import Path

import httpx
import xxhash
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

_backend = Path(__file__).parent.parent / "backend"
if not _backend.exists():
    _backend = Path("/app")
sys.path.insert(0, str(_backend))

from app.config import settings
from app.embeddings import FashionCLIPEmbedder
from app.models import Base, Product, ProductImage, Embedding

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PILOT_TENANT_ID = settings.pilot_tenant_id


async def fetch_image(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        r = await client.get(url, follow_redirects=True, timeout=20)
        r.raise_for_status()
        return r.content
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def parse_price(val: str) -> int | None:
    try:
        return int(float(val.replace(",", "").strip()) * 100)
    except Exception:
        return None


async def upsert_product(session: AsyncSession, row: dict) -> uuid.UUID:
    stmt = pg_insert(Product).values(
        id=uuid.uuid4(),
        tenant_id=PILOT_TENANT_ID,
        external_id=row["external_id"],
        title=row.get("title"),
        brand=row.get("brand"),
        category=row.get("category"),
        price_cents=parse_price(row.get("price", "")),
        currency=row.get("currency", "INR"),
        availability=row.get("availability", "in_stock"),
        url=row.get("url"),
        attributes={"color": row.get("color", "")} if row.get("color") else {},
    ).on_conflict_do_update(
        constraint="uq_products_tenant_external",
        set_={"title": row.get("title"), "updated_at": text("now()")},
    ).returning(Product.id)
    result = await session.execute(stmt)
    return result.scalar_one()


async def run(csv_path: str, batch_size: int, db_url: str):
    engine = create_async_engine(db_url, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    embedder = FashionCLIPEmbedder()

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    logger.info("Loaded %d rows from %s", len(rows), csv_path)
    stats = {"processed": 0, "embedded": 0, "skipped": 0, "failed": 0}

    async with httpx.AsyncClient() as client:
        for batch_start in range(0, len(rows), batch_size):
            batch = rows[batch_start : batch_start + batch_size]
            raw_images: list[bytes | None] = []
            product_ids: list[uuid.UUID] = []

            async with SessionLocal() as session:
                for row in batch:
                    product_id = await upsert_product(session, row)
                    product_ids.append(product_id)
                    img_url = row.get("image_url", "").strip()
                    raw_images.append(await fetch_image(client, img_url) if img_url else None)
                await session.commit()

            valid = [(i, product_ids[i], batch[i], raw_images[i])
                     for i in range(len(batch)) if raw_images[i] is not None]
            if not valid:
                stats["skipped"] += len(batch)
                continue

            try:
                embeddings, hashes = embedder.embed_bytes_batch([v[3] for v in valid])
            except Exception as e:
                logger.error("Batch embed failed: %s", e)
                stats["failed"] += len(valid)
                continue

            async with SessionLocal() as session:
                for (orig_i, product_id, row, raw), embedding, content_hash in zip(valid, embeddings, hashes):
                    existing = await session.execute(
                        select(ProductImage.id).where(
                            ProductImage.tenant_id == PILOT_TENANT_ID,
                            ProductImage.product_id == product_id,
                            ProductImage.content_hash == content_hash,
                            ProductImage.status == "embedded",
                        )
                    )
                    if existing.scalar_one_or_none():
                        stats["skipped"] += 1
                        continue
                    pi = ProductImage(
                        tenant_id=PILOT_TENANT_ID, product_id=product_id,
                        source_url=row.get("image_url", "").strip(),
                        content_hash=content_hash, status="embedded",
                    )
                    session.add(pi)
                    await session.flush()
                    session.add(Embedding(
                        tenant_id=PILOT_TENANT_ID, product_id=product_id,
                        product_image_id=pi.id, model_id=settings.model_id,
                        embedding=embedding.tolist(),
                    ))
                    stats["embedded"] += 1
                await session.commit()

            stats["processed"] += len(batch)
            logger.info("Progress: %d/%d | %s", min(batch_start + batch_size, len(rows)), len(rows), stats)

    await engine.dispose()
    logger.info("Done. %s", stats)


def main():
    parser = argparse.ArgumentParser(description="Bulk embed a CSV product catalog")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--db-url", default=settings.database_url)
    args = parser.parse_args()
    asyncio.run(run(args.csv, args.batch_size, args.db_url))


if __name__ == "__main__":
    main()
