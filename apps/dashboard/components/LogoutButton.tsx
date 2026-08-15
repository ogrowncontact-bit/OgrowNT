"use client";

import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <button
      onClick={handleLogout}
      className="rounded border border-base-600 px-3 py-1.5 text-xs text-ink-300 transition hover:border-signal-red hover:text-signal-red"
    >
      Sign out
    </button>
  );
}
