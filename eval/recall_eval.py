"""
Recall@K evaluation harness (JSONL format).

Usage:
  python eval/recall_eval.py --queries eval/queries.jsonl --api http://localhost:8000

queries.jsonl format (one JSON object per line):
  {
    "query_image_path": "eval/images/query_001.jpg",
    "acceptable_product_ids": ["prd_abc"],
    "acceptable_external_ids": ["MNY-K-5821"],
    "category_hint": "kurta"
  }
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

KS = [1, 5, 10]


async def search_one(client: httpx.AsyncClient, query: dict, limit: int = 10) -> list[dict]:
    img_path = Path(query["query_image_path"])
    if not img_path.exists():
        print(f"  SKIP missing: {img_path}", file=sys.stderr)
        return []
    params: dict[str, Any] = {"limit": str(limit)}
    if query.get("category_hint"):
        params["category"] = query["category_hint"]
    try:
        with open(img_path, "rb") as f:
            resp = await client.post(
                "/v1/search/visual",
                files={"image": (img_path.name, f, "image/jpeg")},
                data=params, timeout=30,
            )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as e:
        print(f"  ERROR {img_path.name}: {e}", file=sys.stderr)
        return []


async def run_eval(queries_path: Path, api: str) -> None:
    with open(queries_path, encoding="utf-8") as f:
        queries = [json.loads(line) for line in f if line.strip()]

    print(f"Evaluating {len(queries)} queries against {api}\n")
    recall_hits: dict[int, int] = {k: 0 for k in KS}
    category_hits = 0
    valid = 0

    async with httpx.AsyncClient(base_url=api) as client:
        for i, q in enumerate(queries, 1):
            acceptable_ids = set(q.get("acceptable_product_ids", []))
            acceptable_ext_ids = set(q.get("acceptable_external_ids", []))
            if not acceptable_ids and not acceptable_ext_ids:
                continue
            results = await search_one(client, q, limit=max(KS))
            if not results:
                continue
            valid += 1
            for k in KS:
                if any(
                    str(r.get("product_id", "")) in acceptable_ids or r.get("external_id", "") in acceptable_ext_ids
                    for r in results[:k]
                ):
                    recall_hits[k] += 1
            if q.get("category_hint") and results and results[0].get("category") == q["category_hint"]:
                category_hits += 1
            if i % 10 == 0:
                print(f"  Processed {i}/{len(queries)}...")

    print(f"\n=== Results ({valid} valid queries) ===")
    for k in KS:
        pct = recall_hits[k] / valid * 100 if valid else 0
        print(f"  Recall@{k:<2} = {recall_hits[k]}/{valid} = {pct:.1f}%")
    cat_pct = category_hits / valid * 100 if valid else 0
    print(f"  Category P@1   = {category_hits}/{valid} = {cat_pct:.1f}%")
    print()
    print(f"  MVP Recall@1  >= 35%: {'PASS' if valid and recall_hits[1]/valid >= 0.35 else 'FAIL'}")
    print(f"  MVP Recall@10 >= 65%: {'PASS' if valid and recall_hits[10]/valid >= 0.65 else 'FAIL'}")
    print(f"  MVP Cat P@1   >= 85%: {'PASS' if valid and category_hits/valid >= 0.85 else 'FAIL'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", required=True)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    queries_path = Path(args.queries)
    if not queries_path.exists():
        print(f"Not found: {queries_path}", file=sys.stderr)
        sys.exit(1)
    asyncio.run(run_eval(queries_path, args.api.rstrip("/")))


if __name__ == "__main__":
    main()
