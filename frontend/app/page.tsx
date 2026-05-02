"use client";

import { useState, useCallback, useRef } from "react";
import { ImageUploader } from "@/components/ImageUploader";
import { SearchResults, SearchResultsSkeleton } from "@/components/SearchResults";
import { SearchFilters } from "@/components/SearchFilters";

export interface SearchResult {
  product_id: string;
  external_id: string;
  title: string | null;
  url: string | null;
  image_url: string | null;
  price: number | null;
  currency: string | null;
  category: string | null;
  score: number;
  score_components: {
    visual: number;
    category_match: number;
    color_match: number;
    popularity: number;
    availability_boost: number;
    business_boost: number;
  };
}

export interface SearchResponse {
  request_id: string;
  results: SearchResult[];
  result_count: number;
  confidence: "high" | "medium" | "low";
  fallback_used: boolean;
  latency_ms: number;
}

export interface Filters {
  category: string;
  price_max: string;
  availability: string;
}

type State = "idle" | "searching" | "results" | "error";

export default function Home() {
  const [state, setState] = useState<State>("idle");
  const [preview, setPreview] = useState<string | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({ category: "", price_max: "", availability: "" });
  const fileRef = useRef<File | null>(null);

  const handleImage = useCallback(async (file: File) => {
    fileRef.current = file;
    setPreview(URL.createObjectURL(file));
    setState("searching");
    setError(null);
    setResponse(null);

    const form = new FormData();
    form.append("image", file);
    if (filters.category) form.append("category", filters.category);
    if (filters.price_max) form.append("price_max", filters.price_max);
    if (filters.availability) form.append("availability", filters.availability);
    form.append("limit", "24");

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/v1/search/visual`, { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: { message: res.statusText } }));
        throw new Error(err?.error?.message || res.statusText);
      }
      setResponse(await res.json());
      setState("results");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed. Please try again.");
      setState("error");
    }
  }, [filters]);

  const handleReset = () => { setState("idle"); setPreview(null); setResponse(null); setError(null); fileRef.current = null; };
  const handleReSearch = useCallback(() => { if (fileRef.current) handleImage(fileRef.current); }, [handleImage]);

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header onReset={state !== "idle" ? handleReset : undefined} />
      <main className="flex-1 w-full max-w-[1440px] mx-auto px-6 sm:px-10 pb-20">
        {state === "idle" && <IdleView filters={filters} onFiltersChange={setFilters} onImage={handleImage} />}
        {state === "searching" && <SearchingView preview={preview} />}
        {(state === "results" || state === "error") && (
          <ResultsView state={state} preview={preview} response={response} error={error} onRetry={handleReSearch} onReset={handleReset} />
        )}
      </main>
    </div>
  );
}

function IdleView({ filters, onFiltersChange, onImage }: { filters: Filters; onFiltersChange: (f: Filters) => void; onImage: (file: File) => void }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-56px)] gap-8 py-12">
      <div className="flex flex-col items-center gap-6 w-full max-w-xl">
        <h1 className="text-[1.0625rem] font-semibold text-foreground tracking-tight">Find by image</h1>
        <SearchFilters filters={filters} onChange={onFiltersChange} />
        <div className="w-full max-w-sm sm:max-w-md">
          <ImageUploader onImage={onImage} />
        </div>
        <p className="label-caps text-muted-foreground">JPEG&nbsp;&nbsp;PNG&nbsp;&nbsp;WebP&nbsp;&nbsp;·&nbsp;&nbsp;10 MB max</p>
      </div>
    </div>
  );
}

function SearchingView({ preview }: { preview: string | null }) {
  return (
    <div className="flex flex-col gap-6 pt-8">
      <div className="flex items-center gap-4 border-b border-border pb-6">
        {preview && (
          <div className="relative shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="Query garment" className="w-14 h-14 object-cover rounded border border-border" />
            <div className="absolute inset-0 rounded bg-background/50 flex items-center justify-center"><Spinner /></div>
          </div>
        )}
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium text-foreground">Searching catalog</p>
          <p className="text-xs text-muted-foreground">Visual embedding · nearest-neighbour retrieval</p>
        </div>
      </div>
      <SearchResultsSkeleton count={12} />
    </div>
  );
}

function ResultsView({ state, preview, response, error, onRetry, onReset }: {
  state: "results" | "error"; preview: string | null; response: SearchResponse | null;
  error: string | null; onRetry: () => void; onReset: () => void;
}) {
  return (
    <div className="flex flex-col gap-6 pt-8">
      <div className="flex items-center gap-5 border-b border-border pb-5">
        {preview && <img src={preview} alt="Query garment" className="shrink-0 w-12 h-12 object-cover rounded border border-border" />}
        <div className="flex flex-1 flex-wrap items-center gap-x-4 gap-y-2 min-w-0">
          <span className="text-sm font-medium text-foreground tabular">
            {state === "error" ? "Search failed" : `${response?.result_count ?? 0} result${response?.result_count !== 1 ? "s" : ""}`}
          </span>
          {response && <>
            <ConfidenceBadge confidence={response.confidence} />
            <span className="label-caps text-muted-foreground tabular">{response.latency_ms} ms</span>
          </>}
          {response?.confidence === "low" && (
            <span className="text-xs text-muted-foreground border border-border rounded px-2 py-0.5">Try a tighter crop or fewer filters</span>
          )}
          {state === "error" && error && <span className="text-xs text-destructive">{error}</span>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={onRetry} className="h-7 px-3 text-xs font-medium rounded border border-border text-foreground hover:bg-secondary transition-colors duration-100">Retry</button>
          <button onClick={onReset} className="h-7 px-3 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/80 transition-colors duration-100">New photo</button>
        </div>
      </div>
      {response?.results && response.results.length > 0 && <SearchResults results={response.results} />}
      {response?.results.length === 0 && <EmptyState />}
    </div>
  );
}

function Header({ onReset }: { onReset?: () => void }) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur-sm">
      <div className="max-w-[1440px] mx-auto px-6 sm:px-10 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 rounded flex items-center justify-center shrink-0 border border-border">
            <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-foreground">
              <path d="M10 3.5H5.5a2 2 0 0 0 0 4h3a2 2 0 0 1 0 4H4" />
            </svg>
          </div>
          <div className="flex items-baseline gap-2.5">
            <span className="text-sm font-semibold tracking-[-0.01em] text-foreground">StyleSync</span>
            <span className="hidden sm:inline label-caps text-muted-foreground">Visual Search</span>
          </div>
        </div>
        {onReset && (
          <button onClick={onReset} className="label-caps text-muted-foreground hover:text-foreground transition-colors duration-100 rounded px-1">New search</button>
        )}
      </div>
    </header>
  );
}

function Spinner() {
  return <div className="w-4 h-4 rounded-full border-[1.5px] border-foreground/20 border-t-foreground animate-spin" role="status" aria-label="Searching" />;
}

function ConfidenceBadge({ confidence }: { confidence: "high" | "medium" | "low" }) {
  const styles = { high: "text-foreground border-border", medium: "text-muted-foreground border-border", low: "text-destructive border-destructive/40" };
  return <span className={`label-caps border rounded px-1.5 py-0.5 ${styles[confidence]}`}>{confidence}</span>;
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-5 py-24 text-center">
      <div className="w-10 h-10 rounded border border-border flex items-center justify-center">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground">
          <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /><line x1="8" y1="11" x2="14" y2="11" />
        </svg>
      </div>
      <div className="flex flex-col gap-1.5">
        <p className="text-sm font-medium text-foreground">No matches</p>
        <p className="text-xs text-muted-foreground max-w-[260px] leading-relaxed">Try a tighter crop, fewer filters, or check that the catalog has been ingested.</p>
      </div>
    </div>
  );
}
