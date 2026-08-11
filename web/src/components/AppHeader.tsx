"use client";

import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import type { Membership } from "@/lib/types";

const NAV_LINKS = [
  { href: "/inbox", label: "Inbox" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/services", label: "Serviços" },
  { href: "/automations", label: "Automações" },
  { href: "/settings", label: "WhatsApp" },
  { href: "/profile", label: "Perfil" },
  { href: "/billing", label: "Assinatura" },
] as const;

export function AppHeader({
  active,
  businessId,
  memberships,
  onBusinessChange,
}: {
  active: "inbox" | "dashboard" | "services" | "automations" | "settings" | "profile" | "billing";
  businessId: string | null;
  memberships: Membership[];
  onBusinessChange: (id: string) => void;
}) {
  const { user, logout } = useAuth();

  return (
    <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-2.5 dark:border-zinc-800">
      <div className="flex items-center gap-4">
        <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">AI Front Desk</span>
        <nav className="flex items-center gap-3 text-sm">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={
                active === link.href.slice(1)
                  ? "font-medium text-zinc-900 dark:text-zinc-50"
                  : "text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
              }
            >
              {link.label}
            </Link>
          ))}
        </nav>
        {memberships.length > 1 ? (
          <select
            value={businessId ?? ""}
            onChange={(e) => onBusinessChange(e.target.value)}
            className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            {memberships.map((m) => (
              <option key={m.business.id} value={m.business.id}>
                {m.business.name}
              </option>
            ))}
          </select>
        ) : (
          <span className="text-sm text-zinc-500">{memberships[0]?.business.name}</span>
        )}
      </div>
      <div className="flex items-center gap-3 text-sm text-zinc-500">
        <span>{user?.name}</span>
        <button onClick={logout} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200">
          Sair
        </button>
      </div>
    </header>
  );
}
