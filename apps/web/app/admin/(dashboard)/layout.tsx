import Link from "next/link";
import { requireAdmin } from "@/lib/adminAuth";
import { AdminLogoutButton } from "@/components/AdminLogoutButton";

export default async function AdminDashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await requireAdmin();

  return (
    <div className="min-h-dvh bg-[var(--inner-paper)]">
      <header className="border-b border-[var(--inner-line)] bg-[var(--inner-card)]">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-6">
            <Link href="/admin" className="font-display text-[17px] text-[var(--inner-ink)]">
              INNER Admin
            </Link>
            <nav className="hidden gap-5 text-[14px] text-[var(--inner-ink-soft)] sm:flex">
              <Link href="/admin/assessments" className="hover:text-[var(--inner-ink)]">
                Assessments
              </Link>
              <Link href="/admin/analytics" className="hover:text-[var(--inner-ink)]">
                Analytics
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[13px] text-[var(--inner-muted)]">
              {session.email} · {session.role}
            </span>
            <AdminLogoutButton />
          </div>
        </div>
        <nav className="flex gap-5 border-t border-[var(--inner-line)] px-6 py-2 text-[13px] text-[var(--inner-ink-soft)] sm:hidden">
          <Link href="/admin/assessments">Assessments</Link>
          <Link href="/admin/analytics">Analytics</Link>
        </nav>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-8">{children}</main>
    </div>
  );
}
