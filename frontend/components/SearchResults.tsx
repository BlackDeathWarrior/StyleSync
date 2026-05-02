"use client";

import type { SearchResult } from "@/app/page";

export function SearchResults({ results }: { results: SearchResult[] }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-px bg-border" role="list" aria-label="Search results">
      {results.map((r) => <ResultCard key={r.product_id} result={r} />)}
    </div>
  );
}

function ResultCard({ result }: { result: SearchResult }) {
  const price = result.price != null
    ? new Intl.NumberFormat("en-IN", { style: "currency", currency: result.currency ?? "INR", maximumFractionDigits: 0 }).format(result.price / 100)
    : null;

  const card = (
    <div className="group flex flex-col bg-card overflow-hidden hover:bg-secondary transition-colors duration-100" role="listitem">
      <div className="relative aspect-[3/4] bg-muted overflow-hidden">
        {result.image_url
          ? <img src={result.image_url} alt={result.title ?? result.external_id} className="absolute inset-0 w-full h-full object-cover" loading="lazy" />
          : <div className="absolute inset-0 flex items-center justify-center"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground/30"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg></div>
        }
        <span className="absolute top-2 right-2 font-mono text-[10px] tabular bg-background/80 text-muted-foreground border border-border/60 rounded px-1 py-px leading-none">
          {Math.round(result.score * 100)}
        </span>
      </div>
      <div className="px-3 pt-2.5 pb-3 flex flex-col gap-1 min-w-0">
        {result.category && <span className="label-caps text-muted-foreground truncate">{result.category}</span>}
        <p className="text-xs text-foreground leading-snug line-clamp-2">{result.title ?? result.external_id}</p>
        {price && <p className="text-xs font-medium text-foreground tabular mt-0.5">{price}</p>}
      </div>
    </div>
  );

  return result.url
    ? <a href={result.url} target="_blank" rel="noopener noreferrer" className="block focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" aria-label={`View ${result.title ?? result.external_id}${price ? `, ${price}` : ""}`}>{card}</a>
    : card;
}

export function SearchResultsSkeleton({ count = 12 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-px bg-border" aria-busy="true" aria-label="Loading results">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex flex-col bg-card overflow-hidden" aria-hidden="true">
          <div className="aspect-[3/4] skeleton" />
          <div className="px-3 pt-2.5 pb-3 flex flex-col gap-2">
            <div className="h-2 w-1/3 rounded-sm skeleton" />
            <div className="h-3 w-full rounded-sm skeleton" />
            <div className="h-3 w-2/3 rounded-sm skeleton" />
            <div className="h-3 w-1/4 rounded-sm skeleton mt-0.5" />
          </div>
        </div>
      ))}
    </div>
  );
}
