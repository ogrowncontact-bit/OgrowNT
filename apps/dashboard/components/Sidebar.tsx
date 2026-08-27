"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// "PROMPT 14" §4's literal sidebar list is Command Center/Markets/
// Opportunities/Portfolio/Risk/Strategies/Agents/Research/Learning/News/
// Execution/Events/System/Audit/Settings (15 items) — Data (§56),
// Incidents (§59), and Alerts (§63) are separately mandated as their own
// routed pages later in the same spec but never added back to §4's list;
// included here anyway so they're actually reachable, a documented,
// deliberate extension of the literal item count rather than an omission.
const NAV_ITEMS: { href: string; label: string }[] = [
  { href: "/command-center", label: "Command Center" },
  { href: "/command-center/markets", label: "Markets" },
  { href: "/command-center/opportunities", label: "Opportunities" },
  { href: "/command-center/portfolio", label: "Portfolio" },
  { href: "/command-center/risk", label: "Risk" },
  { href: "/command-center/strategies", label: "Strategies" },
  { href: "/command-center/agents", label: "Agents" },
  { href: "/command-center/research", label: "Research" },
  { href: "/command-center/learning", label: "Learning" },
  { href: "/command-center/news", label: "News" },
  { href: "/command-center/execution", label: "Execution" },
  { href: "/command-center/events", label: "Events" },
  { href: "/command-center/system", label: "System" },
  { href: "/command-center/data", label: "Data" },
  { href: "/command-center/incidents", label: "Incidents" },
  { href: "/command-center/alerts", label: "Alerts" },
  { href: "/command-center/audit", label: "Audit" },
  { href: "/command-center/settings", label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <nav className="flex h-full w-48 shrink-0 flex-col gap-0.5 border-r border-base-700 bg-base-950 p-3">
      <p className="mb-2 px-2 text-[10px] uppercase tracking-wider text-ink-500">OgrowNT</p>
      {NAV_ITEMS.map((item) => {
        const active = item.href === "/command-center" ? pathname === item.href : pathname?.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`rounded px-2 py-1.5 text-xs transition-colors ${
              active ? "bg-base-700 text-ink-100" : "text-ink-300 hover:bg-base-800 hover:text-ink-100"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
      <div className="mt-auto pt-3">
        <Link href="/dashboard" className="block px-2 py-1.5 text-[10px] text-ink-500 hover:text-ink-300">
          legacy full-page view
        </Link>
      </div>
    </nav>
  );
}
