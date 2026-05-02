#!/usr/bin/env python3
"""
Recall@K evaluation harness for StyleSync.

Usage:
    python eval/eval.py --queries eval/queries.csv --api http://localhost:8000

queries.csv format:
    query_image_path,expected_external_ids  (comma-sep list of acceptable matches)
"""

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from statistics import mean, median

import httpx


def recall_at_k(results: list[str], expected: list[str], k: int) -> float:
    return 1.0 if set(results[:k]) & set(expected) else 0.0


def ndcg_at_k(results: list[str], expected: list[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(results[:k]) if r in expected)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(expected), k)))
    return dcg / ideal if ideal > 0 else 0.0


def run_eval(queries_csv: str, api_base: str, category_filter: str | None = None) -> dict:
    queries = []
    with open(queries_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            queries.append({
                "image_path": row["query_image_path"],
                "expected": [x.strip() for x in row["expected_external_ids"].split(",")],
            })

    print(f"Evaluating {len(queries)} queries against {api_base}")
    r1s, r5s, r10s, ndcg10s, latencies = [], [], [], [], []

    with httpx.Client(timeout=30) as client:
        for i, q in enumerate(queries):
            img_path = Path(q["image_path"])
            if not img_path.exists():
                print(f"  [SKIP] {img_path} not found")
                continue
            with open(img_path, "rb") as f:
                raw = f.read()
            suffix = img_path.suffix.lower()
            mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(suffix, "image/jpeg")
            t0 = time.perf_counter()
            try:
                resp = client.post(
                    f"{api_base}/v1/search/visual",
                    files={"image": (img_path.name, raw, mime)},
                    data={"category": category_filter} if category_filter else {},
                )
                resp.raise_for_status()
            except Exception as e:
                print(f"  [ERROR] Query {i}: {e}")
                continue
            latency_ms = int((time.perf_counter() - t0) * 1000)
            latencies.append(latency_ms)
            returned_ids = [r["external_id"] for r in resp.json().get("results", [])]
            r1s.append(recall_at_k(returned_ids, q["expected"], 1))
            r5s.append(recall_at_k(returned_ids, q["expected"], 5))
            r10s.append(recall_at_k(returned_ids, q["expected"], 10))
            ndcg10s.append(ndcg_at_k(returned_ids, q["expected"], 10))
            print(f"  [{i+1:3d}/{len(queries)}] R@1={r1s[-1]:.0f} R@10={r10s[-1]:.0f} nDCG@10={ndcg10s[-1]:.2f} lat={latency_ms}ms")

    if not r1s:
        print("No results.")
        return {}

    report = {
        "n_queries": len(r1s),
        "recall_at_1": round(mean(r1s), 4),
        "recall_at_5": round(mean(r5s), 4),
        "recall_at_10": round(mean(r10s), 4),
        "ndcg_at_10": round(mean(ndcg10s), 4),
        "latency_p50_ms": int(median(latencies)),
        "latency_p95_ms": int(sorted(latencies)[int(len(latencies) * 0.95)]),
    }
    print("\n=== Eval Report ===")
    for k, v in report.items():
        print(f"  {k}: {v}")
    print("\n=== Target Check ===")
    for label, passed in [
        ("Recall@1 >= 0.35", report["recall_at_1"] >= 0.35),
        ("Recall@10 >= 0.65", report["recall_at_10"] >= 0.65),
        ("nDCG@10 >= 0.55", report["ndcg_at_10"] >= 0.55),
        ("p95 latency <= 2500ms", report["latency_p95_ms"] <= 2500),
    ]:
        print(f"  {'✓' if passed else '✗'} {label}")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default="eval/queries.csv")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--category", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    report = run_eval(args.queries, args.api, args.category)
    if args.output and report:
        Path(args.output).write_text(json.dumps(report, indent=2))
        print(f"\nReport written to {args.output}")


if __name__ == "__main__":
    main()
