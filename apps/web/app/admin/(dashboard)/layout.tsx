import Link from "next/link";
import { requireAdmin, ADMIN_ROLE_LABELS } from "@/lib/adminAuth";
import { AdminLogoutButton } from "@/components/AdminLogoutButton";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { AdminTopBar } from "@/components/admin/AdminTopBar";

export default async function AdminDashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await requireAdmin();

  return (
    <div className="min-h-dvh bg-[var(--inner-paper)]">
      <header className="border-b border-[var(--inner-line)] bg-[var(--inner-card)]">
        <div className="flex items-center justify-between px-6 py-4">
          <Link href="/admin" className="font-display text-[17px] text-[var(--inner-ink)]">
            INNER Master Control Center
          </Link>
          <div className="flex items-center gap-4">
            <AdminTopBar />
            <span className="hidden text-[13px] text-[var(--inner-muted)] sm:inline">
              {session.email} · {ADMIN_ROLE_LABELS[session.role]}
            </span>
            <AdminLogoutButton />
          </div>
        </div>
      </header>
      <div className="flex min-h-[calc(100dvh-65px)] flex-col md:flex-row">
        <AdminSidebar />
        <main className="min-w-0 flex-1 px-6 py-8">{children}</main>
      </div>
    </div>
  );
}
