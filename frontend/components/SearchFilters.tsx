"use client";

import type { Filters } from "@/app/page";

const CATEGORIES = ["saree","kurta","sherwani","lehenga","dupatta","suit","dhoti","anarkali","kurti","other"];

interface Props { filters: Filters; onChange: (f: Filters) => void; }

export function SearchFilters({ filters, onChange }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  return (
    <div className="flex flex-wrap items-center gap-2 max-w-lg w-full" role="group" aria-label="Search filters">
      <FilterSelect id="filter-category" label="Category" value={filters.category} onChange={(v) => set({ category: v })}>
        <option value="">All categories</option>
        {CATEGORIES.map((c) => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
      </FilterSelect>
      <FilterSelect id="filter-price" label="Max price" value={filters.price_max} onChange={(v) => set({ price_max: v })}>
        <option value="">Any price</option>
        <option value="2000">Under ₹2,000</option>
        <option value="5000">Under ₹5,000</option>
        <option value="10000">Under ₹10,000</option>
        <option value="20000">Under ₹20,000</option>
        <option value="50000">Under ₹50,000</option>
      </FilterSelect>
      <FilterSelect id="filter-avail" label="Availability" value={filters.availability} onChange={(v) => set({ availability: v })}>
        <option value="">Any availability</option>
        <option value="in_stock">In stock</option>
        <option value="low">Low stock</option>
      </FilterSelect>
      {(filters.category || filters.price_max || filters.availability) && (
        <button onClick={() => onChange({ category: "", price_max: "", availability: "" })} className="label-caps text-muted-foreground hover:text-foreground transition-colors duration-100 rounded px-1">Clear</button>
      )}
    </div>
  );
}

function FilterSelect({ id, label, value, onChange, children }: { id: string; label: string; value: string; onChange: (v: string) => void; children: React.ReactNode }) {
  return (
    <div className="relative">
      <label htmlFor={id} className="sr-only">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className={["appearance-none h-7 pl-2.5 pr-6 rounded text-[11px] font-medium tracking-wide","border transition-colors duration-100 cursor-pointer bg-background","focus:outline-none focus-visible:ring-1 focus-visible:ring-ring",
          value ? "border-foreground text-foreground" : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground",
        ].join(" ")}>{children}</select>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none opacity-60" aria-hidden="true"><polyline points="6 9 12 15 18 9" /></svg>
    </div>
  );
}
