"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { WhatsAppSettingsView } from "@/components/settings/WhatsAppSettingsView";
import { useAuth } from "@/context/AuthContext";
import { useActiveBusiness } from "@/hooks/useActiveBusiness";

export default function SettingsPage() {
  const { token, user, memberships, loading } = useAuth();
  const router = useRouter();
  const { businessId, setBusinessId } = useActiveBusiness(memberships);

  useEffect(() => {
    if (!loading && !token) router.replace("/login");
  }, [loading, token, router]);

  if (loading || !token || !user) {
    return <div className="flex flex-1 items-center justify-center text-sm text-zinc-400">Carregando...</div>;
  }

  if (memberships.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-zinc-400">
        Sua conta ainda nao esta vinculada a nenhuma empresa.
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <AppHeader active="settings" businessId={businessId} memberships={memberships} onBusinessChange={setBusinessId} />
      {businessId && <WhatsAppSettingsView key={businessId} businessId={businessId} token={token} />}
    </div>
  );
}
