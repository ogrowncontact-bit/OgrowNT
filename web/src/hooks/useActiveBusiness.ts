"use client";

import { useState } from "react";
import type { Membership } from "@/lib/types";

// Deriva a empresa ativa a partir das memberships em vez de sincronizar via
// effect: se o usuario ainda nao escolheu explicitamente, usa a primeira.
export function useActiveBusiness(memberships: Membership[]) {
  const [selected, setSelected] = useState<string | null>(null);
  const businessId = selected ?? memberships[0]?.business.id ?? null;
  return { businessId, setBusinessId: setSelected };
}
