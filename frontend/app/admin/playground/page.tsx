"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, RankingWeights, TenantOut } from "@/lib/api";
import type { SearchResponse } from "@/app/page";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_WEIGHTS: Required<RankingWeights> = {
  w_visual: 0.65, w_category: 0.15, w_color: 0.05,
  w_popularity: 0.05, w_availability: 0.05, w_boost: 0.05,
};

const LABELS: Record<keyof Required<RankingWeights>, string> = {
  w_visual: "Visual similarity", w_category: "Category match", w_color: "Color match",
  w_popularity: "Popularity", w_availability: "In-stock boost", w_boost: "Business boost",
};

export default function PlaygroundPage() {
  const [weights, setWeights] = useState<Required<RankingWeights>>(DEFAULT_WEIGHTS);
  const [savedWeights, setSavedWeights] = useState<Required<RankingWeights>>(DEFAULT_WEIGHTS);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const fileRef = useRef<File | null>(null);

  useEffect(() => {
    apiFetch<TenantOut>("/v1/admin/tenant").then((t) => {
      const rw = (t.config as { ranking_weights?: RankingWeights } | undefined)?.ranking_weights;
      if (rw) { setWeights({ ...DEFAULT_WEIGHTS, ...rw }); setSavedWeights({ ...DEFAULT_WEIGHTS, ...rw }); }
    }).catch(() => {});
  }, []);

  async function saveWeights() {
    setSaving(true); setSaveMsg(null);
    try {
      await apiFetch("/v1/admin/tenant/ranking-weights", { method: "PATCH", body: JSON.stringify(weights) });
      setSavedWeights({ ...weights }); setSaveMsg("Saved");
    } catch (e: unknown) { setSaveMsg(e instanceof Error ? e.message : "Failed"); }
    finally { setSaving(false); setTimeout(() => setSaveMsg(null), 2000); }
  }

  const runSearch = useCallback(async (file: File) => {
    setSearching(true); setSearchError(null); setResponse(null);
    const form = new FormData();
    form.append("image", file);
    try {
      const res = await fetch(`${API}/v1/search/visual`, { method: "POST", body: form });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
      setResponse(await res.json());
    } catch (e: unknown) { setSearchError(e instanceof Error ? e.message : "Search failed"); }
    finally { setSearching(false); }
  }, []);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    fileRef.current = file;
    setPreview(URL.createObjectURL(file));
    runSearch(file);
  }

  const dirty = JSON.stringify(weights) !== JSON.stringify(savedWeights);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-base font-semibold">Playground</h1>
        <p className="text-xs text-muted-foreground mt-0.5">Upload a query image and tune ranking weights live</p>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6">
        <aside className="flex flex-col gap-6">
          <div className="border border-border rounded p-4 flex flex-col gap-3">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Query image</span>
            <label className="flex flex-col items-center justify-center gap-2 border border-dashed border-border rounded p-6 cursor-pointer hover:bg-secondary/40 transition-colors">
              {preview
                ? <img src={preview} alt="Query" className="w-24 h-24 object-cover rounded" />
                : <><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg><span className="text-xs text-muted-foreground">Click to upload</span></>
              }
              <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={handleFile} />
            </label>
          </div>
          <div className="border border-border rounded p-4 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Ranking weights</span>
              {dirty && <span className="text-[10px] text-yellow-600 dark:text-yellow-400">Unsaved</span>}
            </div>
            {(Object.keys(DEFAULT_WEIGHTS) as Array<keyof Required<RankingWeights>>).map((key) => (
              <div key={key} className="flex flex-col gap-1">
                <div className="flex justify-between text-xs">
                  <span>{LABELS[key]}</span>
                  <span className="tabular-nums text-muted-foreground">{weights[key].toFixed(2)}</span>
                </div>
                <input type="range" min={0} max={1} step={0.01} value={weights[key]}
                  onChange={(e) => setWeights((p) => ({ ...p, [key]: parseFloat(e.target.value) }))}
                  className="w-full accent-primary" />
              </div>
            ))}
            <button onClick={saveWeights} disabled={saving || !dirty}
              className="mt-1 h-8 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/80 disabled:opacity-50 transition-colors">
              {saving ? "Saving…" : saveMsg ?? "Save weights"}
            </button>
          </div>
        </aside>
        <section className="flex flex-col gap-4">
          {searching && <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">{Array.from({ length: 12 }).map((_, i) => <div key={i} className="aspect-square rounded border border-border bg-secondary/30 animate-pulse" />)}</div>}
          {searchError && <div className="text-xs text-destructive border border-destructive/30 rounded px-3 py-2">{searchError}</div>}
          {response && !searching && (
            <>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{response.result_count} results</span>
                <span>{response.latency_ms} ms</span>
                <span className={`border rounded px-1.5 py-0.5 uppercase tracking-wide text-[10px] ${ response.confidence === "low" ? "border-destructive/40 text-destructive" : "border-border" }`}>{response.confidence}</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {response.results.map((r) => (
                  <div key={r.product_id} className="flex flex-col gap-1 border border-border rounded overflow-hidden hover:border-foreground/30 transition-colors">
                    {r.image_url
                      ? <img src={r.image_url} alt={r.title ?? ""} className="aspect-square object-cover w-full" />
                      : <div className="aspect-square bg-secondary/50 flex items-center justify-center text-xs text-muted-foreground">No image</div>
                    }
                    <div className="px-2 pb-2 flex flex-col gap-0.5">
                      <p className="text-xs font-medium leading-tight line-clamp-2">{r.title ?? r.external_id}</p>
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] text-muted-foreground">{r.category ?? "—"}</span>
                        <span className="text-[10px] tabular-nums text-primary font-medium">{r.score.toFixed(3)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          {!response && !searching && !searchError && (
            <div className="flex flex-col items-center justify-center gap-3 py-24 border border-dashed border-border rounded text-center">
              <p className="text-sm font-medium">Upload a query image</p>
              <p className="text-xs text-muted-foreground max-w-xs">Results appear here. Adjust weights and re-upload to compare.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
