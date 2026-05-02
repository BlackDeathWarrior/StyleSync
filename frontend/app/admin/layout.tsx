"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/admin", label: "Catalog" },
  { href: "/admin/analytics", label: "Analytics" },
  { href: "/admin/playground", label: "Playground" },
  { href: "/admin/keys", label: "API Keys" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="max-w-[1280px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2.5 shrink-0">
              <div className="w-6 h-6 rounded border border-border flex items-center justify-center">
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-foreground">
                  <path d="M10 3.5H5.5a2 2 0 0 0 0 4h3a2 2 0 0 1 0 4H4" />
                </svg>
              </div>
              <span className="text-sm font-semibold tracking-[-0.01em]">StyleSync</span>
            </Link>
            <nav className="flex gap-1">
              {NAV.map(({ href, label }) => (
                <Link key={href} href={href} className={`px-3 h-8 flex items-center text-xs font-medium rounded transition-colors duration-100 ${
                  pathname === href ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                }`}>{label}</Link>
              ))}
            </nav>
          </div>
          <span className="text-xs text-muted-foreground border border-border rounded px-2 py-0.5">Pilot</span>
        </div>
      </header>
      <main className="flex-1 max-w-[1280px] w-full mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
