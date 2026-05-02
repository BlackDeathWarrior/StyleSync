"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiKeyOut, ApiKeyCreated } from "@/lib/api";

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKeyOut[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => { try { setKeys(await apiFetch<ApiKeyOut[]>("/v1/admin/api-keys")); } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed"); } };
  useEffect(() => { load(); }, []);

  async function createKey() {
    if (!newKeyName.trim()) return;
    setCreating(true); setError(null);
    try {
      const k = await apiFetch<ApiKeyCreated>("/v1/admin/api-keys", { method: "POST", body: JSON.stringify({ name: newKeyName.trim(), scopes: ["search:read"] }) });
      setCreated(k); setNewKeyName(""); await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setCreating(false); }
  }

  async function revokeKey(id: string) {
    if (!confirm("Revoke this key? This cannot be undone.")) return;
    try { await apiFetch(`/v1/admin/api-keys/${id}`, { method: "DELETE" }); await load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed"); }
  }

  const active = keys.filter((k) => !k.revoked_at);
  const revoked = keys.filter((k) => k.revoked_at);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-base font-semibold">API Keys</h1>
        <p className="text-xs text-muted-foreground mt-0.5">Create and revoke runtime keys. The secret is shown once at creation.</p>
      </div>
      {error && <div className="text-xs text-destructive border border-destructive/30 rounded px-3 py-2">{error}</div>}
      {created && (
        <div className="border border-green-300 dark:border-green-800 rounded p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-green-800 dark:text-green-300">Copy now — not shown again</span>
            <button onClick={() => setCreated(null)} className="text-xs text-muted-foreground hover:text-foreground">Dismiss</button>
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-background border border-border rounded px-3 py-2 font-mono break-all">{created.full_key}</code>
            <button onClick={async () => { await navigator.clipboard.writeText(created.full_key); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
              className="h-8 px-3 text-xs rounded border border-border hover:bg-secondary transition-colors shrink-0">{copied ? "Copied" : "Copy"}</button>
          </div>
        </div>
      )}
      <div className="border border-border rounded p-4 flex flex-col gap-3">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Create key</span>
        <div className="flex gap-2">
          <input type="text" placeholder="Key name (e.g. production-widget)" value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && createKey()}
            className="flex-1 h-8 px-3 text-xs border border-border rounded bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
          <button onClick={createKey} disabled={creating || !newKeyName.trim()}
            className="h-8 px-4 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/80 disabled:opacity-50 transition-colors">
            {creating ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
      <KeyTable title={`Active (${active.length})`} keys={active} onRevoke={revokeKey} showRevoke />
      {revoked.length > 0 && <KeyTable title={`Revoked (${revoked.length})`} keys={revoked} onRevoke={() => {}} showRevoke={false} dimmed />}
    </div>
  );
}

function KeyTable({ title, keys, onRevoke, showRevoke, dimmed }: { title: string; keys: ApiKeyOut[]; onRevoke: (id: string) => void; showRevoke: boolean; dimmed?: boolean }) {
  return (
    <section className={dimmed ? "opacity-60" : ""}>
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">{title}</h2>
      {keys.length === 0
        ? <div className="border border-border rounded px-6 py-8 text-center text-xs text-muted-foreground">No keys. Create one above.</div>
        : <div className="border border-border rounded overflow-hidden"><table className="w-full text-xs">
            <thead><tr className="border-b border-border bg-secondary/30">
              {["Name","Prefix","Scopes","Created","Last used",""].map(h => <th key={h} className="text-left px-3 py-2 text-muted-foreground font-medium">{h}</th>)}
            </tr></thead>
            <tbody>{keys.map((k) => (
              <tr key={k.id} className="border-b border-border last:border-0 hover:bg-secondary/20">
                <td className="px-3 py-2 font-medium">{k.name ?? <span className="text-muted-foreground italic">unnamed</span>}</td>
                <td className="px-3 py-2 font-mono text-muted-foreground">sk_live_{k.key_prefix}…</td>
                <td className="px-3 py-2 text-muted-foreground">{k.scopes.join(", ")}</td>
                <td className="px-3 py-2 text-muted-foreground">{new Date(k.created_at).toLocaleDateString()}</td>
                <td className="px-3 py-2 text-muted-foreground">{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "Never"}</td>
                <td className="px-3 py-2 text-right">{showRevoke && <button onClick={() => onRevoke(k.id)} className="text-xs text-destructive hover:underline">Revoke</button>}</td>
              </tr>
            ))}</tbody>
          </table></div>
      }
    </section>
  );
}
