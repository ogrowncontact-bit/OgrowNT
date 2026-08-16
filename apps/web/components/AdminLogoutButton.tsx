"use client";

import { useRouter } from "next/navigation";

export function AdminLogoutButton() {
  const router = useRouter();
  async function handleLogout() {
    await fetch("/api/admin/logout", { method: "POST" });
    router.push("/admin/login");
    router.refresh();
  }
  return (
    <button onClick={handleLogout} className="text-[13px] text-[var(--inner-muted)] underline underline-offset-4">
      Sign out
    </button>
  );
}
