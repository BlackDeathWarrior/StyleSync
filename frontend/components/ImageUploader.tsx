"use client";

import { useCallback, useRef, useState } from "react";

interface Props { onImage: (file: File) => void; }

export function ImageUploader({ onImage }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const accept = (file: File) => {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) return;
    if (file.size > 10 * 1024 * 1024) return;
    onImage(file);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) accept(file);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onImage]);

  const onPaste = useCallback((e: React.ClipboardEvent) => {
    const item = Array.from(e.clipboardData.items).find((i) => i.type.startsWith("image/"));
    if (item) { const file = item.getAsFile(); if (file) accept(file); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onImage]);

  return (
    <div role="button" tabIndex={0} aria-label="Upload garment image — drag, paste, or click to browse"
      className={["relative w-full border rounded","flex flex-col items-center justify-center gap-4","px-8 py-20 cursor-pointer select-none","transition-colors duration-100","focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        dragOver ? "border-foreground bg-secondary" : "border-border hover:border-foreground/30 hover:bg-secondary/60",
      ].join(" ")}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop} onPaste={onPaste}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round"
        className={dragOver ? "text-foreground" : "text-muted-foreground"} aria-hidden="true">
        <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
        <circle cx="12" cy="13" r="3" />
      </svg>
      <div className="text-center flex flex-col gap-1">
        <p className="text-sm text-foreground">{dragOver ? "Drop to search" : "Drop, paste, or browse"}</p>
        <p className="text-xs text-muted-foreground">Any garment photograph</p>
      </div>
      <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" aria-hidden="true" tabIndex={-1} onChange={(e) => { const f = e.target.files?.[0]; if (f) accept(f); e.target.value = ""; }} />
    </div>
  );
}
