"""
Bulk ingest products from a CSV file into StyleSync.

CSV columns (all optional except external_id and image_url):
  external_id, title, brand, category, subcategory,
  price_cents, currency, availability, popularity_score,
  url, image_url

Usage:
  python scripts/ingest_csv.py --csv data/catalog.csv --api http://localhost:8000
  python scripts/ingest_csv.py --csv data/catalog.csv --api http://localhost:8000 --embed
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

import httpx

DEFAULT_API = "http://localhost:8000"
BATCH = 20


async def ingest(csv_path: Path, api: str, embed: bool) -> None:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Loaded {len(rows)} rows from {csv_path}")

    async with httpx.AsyncClient(base_url=api, timeout=60) as client:
        sem = asyncio.Semaphore(BATCH)

        async def create_one(row: dict) -> dict | None:
            async with sem:
                image_urls = [u.strip() for u in row.get("image_url", "").split("|") if u.strip()]
                payload = {
                    "external_id": row["external_id"].strip(),
                    "title": row.get("title", "").strip() or None,
                    "brand": row.get("brand", "").strip() or None,
                    "category": row.get("category", "").strip() or None,
                    "subcategory": row.get("subcategory", "").strip() or None,
                    "price_cents": int(row["price_cents"]) if row.get("price_cents") else None,
                    "currency": row.get("currency", "INR").strip() or "INR",
                    "availability": row.get("availability", "in_stock").strip() or "in_stock",
                    "popularity_score": float(row["popularity_score"]) if row.get("popularity_score") else None,
                    "url": row.get("url", "").strip() or None,
                    "image_urls": image_urls,
                }
                try:
                    resp = await client.post("/v1/catalog/products", json=payload)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    print(f"  ERROR {row['external_id']}: {e}", file=sys.stderr)
                    return None

        results = await asyncio.gather(*[create_one(r) for r in rows])

    created = [r for r in results if r]
    print(f"Created: {len(created)}  Failed: {len(results) - len(created)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest CSV catalog into StyleSync")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--embed", action="store_true")
    args = parser.parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    asyncio.run(ingest(csv_path, args.api.rstrip("/"), args.embed))


if __name__ == "__main__":
    main()
