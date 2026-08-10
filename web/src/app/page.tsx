"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function Home() {
  const { token, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(token ? "/inbox" : "/login");
  }, [loading, token, router]);

  return (
    <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
      Carregando...
    </div>
  );
}
