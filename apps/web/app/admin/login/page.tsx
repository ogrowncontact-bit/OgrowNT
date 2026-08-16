import { redirect } from "next/navigation";
import { getAdminSession } from "@/lib/adminAuth";
import { AdminLoginForm } from "@/components/AdminLoginForm";

export default async function AdminLoginPage() {
  const session = await getAdminSession();
  if (session) redirect("/admin");

  return (
    <div className="flex min-h-dvh items-center justify-center bg-[var(--inner-paper)] px-6">
      <div className="w-full max-w-sm">
        <p className="mb-1 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">INNER Admin</p>
        <h1 className="font-display mb-8 text-[26px] text-[var(--inner-ink)]">Sign in</h1>
        <AdminLoginForm />
      </div>
    </div>
  );
}
