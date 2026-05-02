"use client";

import { useEffect, useState } from "react";
import { apiFetch, CatalogStats, ProductOut, SyncJobOut } from "@/lib/api";

export default function CatalogPage() {
  const [stats, setStats] = useState<CatalogStats | null>(null);
  const [products, setProducts] = useState<ProductOut[]>([]);
  const [jobs, setJobs] = useState<SyncJobOut[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [s, p, j] = await Promise.all([
        apiFetch<CatalogStats>("/v1/admin/catalog/stats"),
        apiFetch<ProductOut[]>("/v1/admin/catalog/products?limit=50"),
        apiFetch<SyncJobOut[]>("/v1/admin/sync/jobs"),
      ]);
      setStats(s); setProducts(p); setJobs(j);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to load"); }
  }

  useEffect(() => { load(); }, []);

  async function triggerSync() {
    setSyncing(true);
    try { await apiFetch<SyncJobOut>("/v1/admin/sync/trigger", { method: "POST" }); await load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Sync failed"); }
    finally { setSyncing(false); }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold">Catalog</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Products, images, and embedding status</p>
        </div>
        <button onClick={triggerSync} disabled={syncing} className="h-8 px-4 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/80 disabled:opacity-50 transition-colors">
          {syncing ? "Syncing…" : "Trigger sync"}
        </button>
      </div>

      {error && <div className="text-xs text-destructive border border-destructive/30 rounded px-3 py-2">{error}</div>}

      {stats && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {[
              { label: "Products", value: stats.total_products },
              { label: "Images", value: stats.total_images },
              { label: "Embedded", value: stats.embedded, color: "text-green-600 dark:text-green-400" },
              { label: "Pending", value: stats.pending, color: "text-yellow-600 dark:text-yellow-400" },
              { label: "Failed", value: stats.failed, color: stats.failed > 0 ? "text-destructive" : undefined },
            ].map(({ label, value, color }) => (
              <div key={label} className="border border-border rounded p-4 flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">{label}</span>
                <span className={`text-2xl font-semibold tabular-nums ${color ?? "text-foreground"}`}>{value.toLocaleString()}</span>
              </div>
            ))}
          </div>
          {stats.total_images > 0 && (
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Embed progress</span>
                <span>{Math.round((stats.embedded / stats.total_images) * 100)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                <div className="h-full rounded-full bg-primary transition-all duration-500" style={{ width: `${(stats.embedded / stats.total_images) * 100}%` }} />
              </div>
            </div>
          )}
        </>
      )}

      {jobs.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Recent sync jobs</h2>
          <div className="border border-border rounded overflow-hidden">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-border bg-secondary/30">
                <th className="text-left px-3 py-2 text-muted-foreground font-medium">Source</th>
                <th className="text-left px-3 py-2 text-muted-foreground font-medium">Status</th>
                <th className="text-left px-3 py-2 text-muted-foreground font-medium">Started</th>
                <th className="text-left px-3 py-2 text-muted-foreground font-medium">Stats</th>
              </tr></thead>
              <tbody>{jobs.map((job) => (
                <tr key={job.id} className="border-b border-border last:border-0 hover:bg-secondary/20">
                  <td className="px-3 py-2 font-mono">{job.source}</td>
                  <td className="px-3 py-2"><StatusBadge status={job.status} /></td>
                  <td className="px-3 py-2 text-muted-foreground">{job.started_at ? new Date(job.started_at).toLocaleString() : "—"}</td>
                  <td className="px-3 py-2 text-muted-foreground font-mono">{job.stats ? JSON.stringify(job.stats) : "—"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      )}

      <section>
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Products ({products.length})</h2>
        {products.length === 0 ? (
          <div className="border border-border rounded px-6 py-12 flex flex-col items-center gap-2 text-center">
            <p className="text-sm font-medium">No products ingested yet</p>
            <p className="text-xs text-muted-foreground max-w-sm">Use the embed script or API to add products, then run a sync.</p>
          </div>
        ) : (
          <div className="border border-border rounded overflow-hidden"><div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-border bg-secondary/30">
                {["SKU","Title","Category","Price","Availability","Images","Embedded","Pending","Failed"].map(h => (
                  <th key={h} className="text-left px-3 py-2 text-muted-foreground font-medium">{h}</th>
                ))}
              </tr></thead>
              <tbody>{products.map((p) => (
                <tr key={p.id} className="border-b border-border last:border-0 hover:bg-secondary/20">
                  <td className="px-3 py-2 font-mono text-muted-foreground">{p.external_id}</td>
                  <td className="px-3 py-2 max-w-[200px] truncate">{p.title ?? "—"}</td>
                  <td className="px-3 py-2 text-muted-foreground">{p.category ?? "—"}</td>
                  <td className="px-3 py-2 tabular-nums">{p.price_cents != null ? `₹${(p.price_cents/100).toLocaleString()}` : "—"}</td>
                  <td className="px-3 py-2 text-muted-foreground">{p.availability ?? "—"}</td>
                  <td className="px-3 py-2 tabular-nums">{p.image_count}</td>
                  <td className="px-3 py-2 tabular-nums text-green-600 dark:text-green-400">{p.embedded_count}</td>
                  <td className="px-3 py-2 tabular-nums text-yellow-600 dark:text-yellow-400">{p.pending_count}</td>
                  <td className="px-3 py-2 tabular-nums text-destructive">{p.failed_count || "—"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div></div>
        )}
      </section>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    done: "text-green-700 dark:text-green-400 border-green-300 dark:border-green-800",
    running: "text-blue-700 dark:text-blue-400 border-blue-300",
    queued: "text-yellow-700 dark:text-yellow-400 border-yellow-300",
    failed: "text-destructive border-destructive/40",
  };
  return <span className={`border rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${styles[status] ?? "border-border text-muted-foreground"}`}>{status}</span>;
}
