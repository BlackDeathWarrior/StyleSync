"use client";

import { useEffect, useState } from "react";
import { apiFetch, AnalyticsSummary } from "@/lib/api";

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<AnalyticsSummary>("/v1/admin/analytics/summary")
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-base font-semibold">Analytics</h1>
        <p className="text-xs text-muted-foreground mt-0.5">Search performance and quality metrics</p>
      </div>
      {error && <div className="text-xs text-destructive border border-destructive/30 rounded px-3 py-2">{error}</div>}
      {!data && !error && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="border border-border rounded p-4 h-20 animate-pulse bg-secondary/30" />)}
        </div>
      )}
      {data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Searches today" value={data.searches_today.toLocaleString()} />
            <StatCard label="Searches (7 d)" value={data.searches_7d.toLocaleString()} />
            <StatCard label="Avg latency" value={data.avg_latency_ms != null ? `${Math.round(data.avg_latency_ms)} ms` : "—"} />
            <StatCard label="p95 latency" value={data.p95_latency_ms != null ? `${data.p95_latency_ms} ms` : "—"} alert={data.p95_latency_ms != null && data.p95_latency_ms > 2500} />
            <StatCard label="No-result rate" value={`${(data.no_result_rate * 100).toFixed(1)}%`} alert={data.no_result_rate > 0.05} />
            <StatCard label="Low confidence" value={`${(data.low_confidence_rate * 100).toFixed(1)}%`} alert={data.low_confidence_rate > 0.3} />
          </div>
          {data.searches_7d === 0 && (
            <div className="border border-border rounded px-6 py-12 flex flex-col items-center gap-2 text-center">
              <p className="text-sm font-medium">No searches yet</p>
              <p className="text-xs text-muted-foreground max-w-sm">Use the Playground or the widget to run visual searches — metrics appear here.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return (
    <div className={`border rounded p-4 flex flex-col gap-1 ${alert ? "border-destructive/40" : "border-border"}`}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-2xl font-semibold tabular-nums ${alert ? "text-destructive" : "text-foreground"}`}>{value}</span>
    </div>
  );
}
