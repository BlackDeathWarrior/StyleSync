# StyleSync — Visual AI Fashion Search

> Upload a garment photo → get visually similar products from your catalog instantly.

**B2B SaaS visual product search for fashion brands.** StyleSync embeds every catalog image with [FashionCLIP](https://github.com/patrickjohncyh/fashion-clip), indexes them in pgvector, and exposes a Visual Search API plus a drop-in admin dashboard.

---

## Architecture

```
Query image
    │
    ▼
[FastAPI] ─── [Redis cache] ─── [FashionCLIP fp16]
    │
    ▼
[pgvector HNSW ANN]  →  top-200 candidates
    │
    ▼
[Multi-signal ranker]  →  cosine + category + color + popularity + availability + boost
    │
    ▼
Ranked product list  (p95 target: ≤ 1.5 s)
```

```
StyleSync/
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI app + search + catalog endpoints
│   │   ├── admin.py         Admin API (keys, catalog stats, analytics, sync)
│   │   ├── auth.py          API key verification (SHA-256, Redis-cached)
│   │   ├── embeddings.py    FashionCLIP wrapper (fp16, batch embed)
│   │   ├── search.py        pgvector ANN + multi-signal ranker
│   │   ├── schemas.py       Pydantic v2 schemas
│   │   ├── models.py        SQLAlchemy 2 ORM models
│   │   ├── config.py        Settings (pydantic-settings)
│   │   └── database.py      Async SQLAlchemy engine
│   ├── alembic/             DB migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx         Visual search UI (idle → searching → results)
│   │   └── admin/           Admin dashboard
│   │       ├── page.tsx     Catalog tab
│   │       ├── analytics/   Analytics tab
│   │       ├── playground/  Ranking weight playground
│   │       └── keys/        API key management
│   ├── components/          ImageUploader, SearchResults, SearchFilters, shadcn/ui
│   └── lib/api.ts           Typed API client
├── scripts/
│   ├── embed_catalog.py     Bulk catalog ingestion (batched, idempotent)
│   └── ingest_csv.py        CSV → API ingestion helper
├── eval/
│   ├── eval.py              Recall@K + nDCG@10 harness
│   └── recall_eval.py       JSONL-format eval harness
├── data/                    Sample catalogs go here
└── docker-compose.yml
```

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- Node.js 20+
- Python 3.12+ (for scripts)

### 1. Start infrastructure + backend

```bash
cp backend/.env.example backend/.env   # edit if needed
docker compose up --build
```

> First run downloads FashionCLIP (~600 MB) and caches it in a named volume.

Run DB migrations (first time only):

```bash
docker compose exec backend alembic upgrade head
```

Backend API: `http://localhost:8000`  
API docs: `http://localhost:8000/docs`

### 2. Ingest a sample catalog

Create a CSV with columns: `external_id, title, category, price, currency, availability, url, image_url, brand, color`

```bash
python scripts/embed_catalog.py \
  --csv data/catalog.csv \
  --db-url postgresql+asyncpg://stylesync:stylesync@localhost:5432/stylesync
```

Or use the REST API directly:

```bash
curl -X POST http://localhost:8000/v1/catalog/products \
  -H 'Content-Type: application/json' \
  -d '{"external_id":"SKU-001","title":"Blue Kurta","category":"kurta","price_cents":149900,"image_urls":["https://..."],"availability":"in_stock"}'
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

- Visual search: `http://localhost:3000`
- Admin dashboard: `http://localhost:3000/admin`

---

## Visual Search API

```http
POST /v1/search/visual
X-StyleSync-Key: sk_live_<prefix>_<secret>
Content-Type: multipart/form-data

image:        <file>         required
category:     kurta          optional hard filter
price_max:    5000           optional (INR)
availability: in_stock       optional
limit:        24             optional (max 100)
```

**Response:**

```json
{
  "request_id": "req_01HX...",
  "results": [
    {
      "product_id": "...",
      "external_id": "MNY-K-5821",
      "title": "Embroidered Cotton Kurta",
      "url": "https://brand.com/p/MNY-K-5821",
      "image_url": "https://cdn.brand.com/...",
      "price": 249900,
      "currency": "INR",
      "category": "kurta",
      "score": 0.871,
      "score_components": {
        "visual": 0.892,
        "category_match": 1.0,
        "color_match": 0.0,
        "popularity": 0.65,
        "availability_boost": 1.0,
        "business_boost": 0.0
      }
    }
  ],
  "result_count": 24,
  "confidence": "high",
  "latency_ms": 1420
}
```

Confidence: `high` (top-1 ≥ 0.8) · `medium` (0.6–0.8) · `low` (< 0.6 → suggest crop/retry)

---

## Admin API

All admin routes are at `/v1/admin/`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/admin/tenant` | Tenant config |
| PATCH | `/v1/admin/tenant/ranking-weights` | Update ranking weights |
| GET | `/v1/admin/api-keys` | List API keys |
| POST | `/v1/admin/api-keys` | Create API key |
| DELETE | `/v1/admin/api-keys/{id}` | Revoke key |
| GET | `/v1/admin/catalog/stats` | Catalog stats |
| GET | `/v1/admin/catalog/products` | Product list with embed status |
| POST | `/v1/admin/sync/trigger` | Trigger sync job |
| GET | `/v1/admin/sync/jobs` | Sync job history |
| GET | `/v1/admin/analytics/summary` | Search analytics |

---

## Ranking

```
score = w_visual   × cosine_similarity
      + w_category × 1[category_match]
      + w_color    × color_similarity
      + w_pop      × normalize(popularity)
      + w_avail    × 1[in_stock]
      + w_boost    × business_boost
```

Default weights: `w_visual=0.65, w_category=0.15, w_color=0.05, w_pop=0.05, w_avail=0.05, w_boost=0.05`

Per-tenant weights are stored in `tenants.config.ranking_weights` (JSONB) and editable live via the Playground tab.

---

## Evaluation

```bash
# Add query images to eval/images/ and create queries.csv
python eval/eval.py --queries eval/queries.csv --api http://localhost:8000

# JSONL format (supports product_id + external_id matching)
python eval/recall_eval.py --queries eval/queries.jsonl --api http://localhost:8000
```

MVP quality gates:

| Metric | Target |
|--------|--------|
| Recall@1 | ≥ 0.35 |
| Recall@10 | ≥ 0.65 |
| Category Precision@1 | ≥ 0.85 |
| nDCG@10 | ≥ 0.55 |
| Search p95 | ≤ 2.5 s |

---

## Stack

| Layer | Tech |
|-------|------|
| Model | FashionCLIP (`patrickjohncyh/fashion-clip`) fp16 |
| Backend | FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 |
| Vector DB | Postgres 15 + pgvector (HNSW, cosine) |
| Cache | Redis (embedding cache + API key cache) |
| Frontend | Next.js 16 + Tailwind v4 + shadcn/ui |
| Infra | Docker Compose → ECS/Fargate (prod) |

---

## Roadmap

- [ ] **Phase 1 (PoC)** — Single tenant, FashionCLIP + pgvector, CSV ingestion, visual search + admin dashboard ✅
- [ ] **Phase 2 (MVP)** — Multi-tenant, S3 connector, async SQS workers, Cognito auth, Stripe billing, Qdrant migration
- [ ] **Phase 3** — BLIP attribute enrichment, re-ranker, React/iOS/Android SDKs, self-service signup
- [ ] **Future** — LoRA fine-tuning on ethnic wear, outfit completion, text+image hybrid, virtual try-on

---

## License

MIT
