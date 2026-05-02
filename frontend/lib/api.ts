const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export interface TenantOut {
  id: string; name: string; slug: string; plan: string; status: string;
  config: Record<string, unknown>;
}
export interface CatalogStats {
  total_products: number; total_images: number; embedded: number; pending: number; failed: number;
}
export interface ProductOut {
  id: string; external_id: string; title: string | null; category: string | null;
  price_cents: number | null; availability: string | null;
  image_count: number; embedded_count: number; pending_count: number; failed_count: number;
}
export interface SyncJobOut {
  id: string; source: string; status: string; stats: Record<string, number> | null;
  started_at: string | null; finished_at: string | null; error: string | null;
}
export interface AnalyticsSummary {
  searches_today: number; searches_7d: number;
  avg_latency_ms: number | null; p95_latency_ms: number | null;
  no_result_rate: number; low_confidence_rate: number;
  top_categories: Array<{ category: string; count: number }>;
}
export interface ApiKeyOut {
  id: string; name: string | null; key_prefix: string; scopes: string[];
  created_at: string; last_used_at: string | null; revoked_at: string | null;
}
export interface ApiKeyCreated extends ApiKeyOut { full_key: string; }
export interface RankingWeights {
  w_visual?: number; w_category?: number; w_color?: number;
  w_popularity?: number; w_availability?: number; w_boost?: number;
}
