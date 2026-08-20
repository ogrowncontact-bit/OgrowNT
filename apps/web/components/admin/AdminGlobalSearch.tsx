"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { SearchResult } from "@/app/api/admin/search/route";

export function AdminGlobalSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    const handle = setTimeout(async () => {
      const res = await fetch(`/api/admin/search?q=${encodeURIComponent(query)}`);
      if (res.ok) {
        const data = await res.json();
        setResults(data.results ?? []);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function go(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

  return (
    <div ref={containerRef} className="relative w-full max-w-xs">
      <label htmlFor="admin-global-search" className="sr-only">
        Search everything
      </label>
      <input
        id="admin-global-search"
        type="search"
        placeholder="Search discoveries, orders, users…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        className="w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-paper)] px-3 py-1.5 text-[13px] text-[var(--inner-ink)] focus:border-[var(--inner-accent)] focus:outline-none"
      />
      {open && results.length > 0 && (
        <div className="absolute z-20 mt-1 w-full max-h-80 overflow-y-auto rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] shadow-lg">
          {results.map((r, i) => (
            <button
              key={`${r.type}-${i}`}
              onClick={() => go(r.href)}
              className="block w-full border-b border-[var(--inner-line)] px-3 py-2 text-left last:border-0 hover:bg-[var(--inner-paper-dim)]"
            >
              <p className="text-[11px] uppercase tracking-[0.1em] text-[var(--inner-muted)]">{r.type}</p>
              <p className="text-[13px] font-medium text-[var(--inner-ink)]">{r.label}</p>
              <p className="text-[12px] text-[var(--inner-ink-soft)]">{r.sublabel}</p>
            </button>
          ))}
        </div>
      )}
      {open && query.trim().length >= 2 && results.length === 0 && (
        <div className="absolute z-20 mt-1 w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-3 py-2 text-[13px] text-[var(--inner-muted)] shadow-lg">
          No matches.
        </div>
      )}
    </div>
  );
}
