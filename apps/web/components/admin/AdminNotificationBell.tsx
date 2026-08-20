"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { OperationalAlert } from "@/lib/admin/notificationsReader";

export function AdminNotificationBell({ alerts }: { alerts: OperationalAlert[] }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const critical = alerts.filter((a) => a.severity === "critical").length;

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={`Notifications (${alerts.length})`}
        className="relative rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-2.5 py-1.5 text-[13px] text-[var(--inner-ink-soft)]"
      >
        🔔
        {alerts.length > 0 && (
          <span
            className={`absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-medium text-white ${critical > 0 ? "bg-[var(--inner-accent)]" : "bg-[var(--inner-muted)]"}`}
          >
            {alerts.length}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-72 rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] shadow-lg">
          {alerts.length === 0 ? (
            <p className="px-3 py-3 text-[13px] text-[var(--inner-muted)]">No operational alerts.</p>
          ) : (
            alerts.map((a, i) => (
              <Link
                key={i}
                href={a.href}
                onClick={() => setOpen(false)}
                className="block border-b border-[var(--inner-line)] px-3 py-2.5 text-[13px] last:border-0 hover:bg-[var(--inner-paper-dim)]"
              >
                <span className={a.severity === "critical" ? "text-[var(--inner-accent)]" : "text-[var(--inner-ink)]"}>{a.message}</span>
              </Link>
            ))
          )}
        </div>
      )}
    </div>
  );
}
