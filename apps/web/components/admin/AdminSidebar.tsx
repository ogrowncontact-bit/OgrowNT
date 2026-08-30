"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  href: string;
  label: string;
}
interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  { label: "Overview", items: [{ href: "/admin", label: "Overview" }] },
  {
    label: "Content",
    items: [
      { href: "/admin/assessments", label: "Discoveries" },
      { href: "/admin/questions", label: "Questions" },
      { href: "/admin/profiles", label: "Profiles" },
      { href: "/admin/journal", label: "Journal" },
    ],
  },
  {
    label: "AI",
    items: [{ href: "/admin/ai", label: "AI Studio" }],
  },
  {
    label: "Reports",
    items: [
      { href: "/admin/sessions", label: "Sessions" },
      { href: "/admin/reports", label: "Reports" },
      { href: "/admin/qa/love", label: "LOVE QA" },
      { href: "/admin/qa/relationship", label: "Relationship QA" },
      { href: "/admin/launch/love", label: "LOVE Launch" },
      { href: "/admin/feedback", label: "Feedback" },
      { href: "/admin/support", label: "Support" },
    ],
  },
  {
    label: "Commerce",
    items: [
      { href: "/admin/products", label: "Products" },
      { href: "/admin/orders", label: "Orders" },
      { href: "/admin/users", label: "Users" },
    ],
  },
  {
    label: "Growth",
    items: [
      { href: "/admin/email", label: "Emails" },
      { href: "/admin/recommendations", label: "Recommendations" },
      { href: "/admin/campaigns", label: "Campaigns" },
      { href: "/admin/analytics", label: "Analytics" },
      { href: "/admin/experiments", label: "Experiments" },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/admin/demo", label: "Demo Mode" },
      { href: "/admin/settings", label: "Settings" },
      { href: "/admin/audit", label: "Audit Logs" },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/admin") return pathname === "/admin";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="space-y-6">
      {NAV_GROUPS.map((group) => (
        <div key={group.label}>
          <p className="mb-2 px-3 text-[11px] font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">{group.label}</p>
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={`block rounded-[var(--inner-radius-sm)] px-3 py-2 text-[14px] ${
                    active
                      ? "bg-[var(--inner-accent)] font-medium text-[var(--inner-accent-contrast)]"
                      : "text-[var(--inner-ink-soft)] hover:bg-[var(--inner-card)]"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

/**
 * Desktop-first per FASE 25's own MOBILE ADMIN section ("Admin prioritizes
 * desktop... Mobile should remain functional for urgent operations") — a
 * fixed left column at md+ widths, collapsed behind a toggle below that so
 * every route is still reachable on a phone, just not the primary layout.
 */
export function AdminSidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      <div className="border-b border-[var(--inner-line)] px-4 py-2 md:hidden">
        <button
          onClick={() => setMobileOpen((v) => !v)}
          aria-expanded={mobileOpen}
          aria-controls="admin-mobile-nav"
          className="text-[13px] font-medium text-[var(--inner-ink)]"
        >
          {mobileOpen ? "Close menu ✕" : "Menu ☰"}
        </button>
        {mobileOpen && (
          <div id="admin-mobile-nav" className="mt-3 pb-2">
            <NavLinks pathname={pathname} onNavigate={() => setMobileOpen(false)} />
          </div>
        )}
      </div>

      <aside className="hidden w-60 shrink-0 border-r border-[var(--inner-line)] px-3 py-6 md:block">
        <NavLinks pathname={pathname} />
      </aside>
    </>
  );
}
