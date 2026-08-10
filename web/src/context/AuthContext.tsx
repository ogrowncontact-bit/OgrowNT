"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { AuthUser, Membership } from "@/lib/types";

const TOKEN_STORAGE_KEY = "ogrownt.token";

interface RegisterInput {
  email: string;
  password: string;
  name: string;
  businessName: string;
  industry: string;
}

interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;
  memberships: Membership[];
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async (tok: string) => {
    const me = await apiFetch<{ user: AuthUser; memberships: Membership[] }>("/api/auth/me", tok);
    setUser(me.user);
    setMemberships(me.memberships);
  }, []);

  useEffect(() => {
    async function init() {
      const stored = typeof window !== "undefined" ? localStorage.getItem(TOKEN_STORAGE_KEY) : null;
      if (!stored) {
        setLoading(false);
        return;
      }
      setToken(stored);
      try {
        await loadMe(stored);
      } catch {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        setToken(null);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [loadMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await apiFetch<{ token: string }>("/api/auth/login", null, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem(TOKEN_STORAGE_KEY, result.token);
      setToken(result.token);
      await loadMe(result.token);
    },
    [loadMe]
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const result = await apiFetch<{ token: string }>("/api/auth/register", null, {
        method: "POST",
        body: JSON.stringify(input),
      });
      localStorage.setItem(TOKEN_STORAGE_KEY, result.token);
      setToken(result.token);
      await loadMe(result.token);
    },
    [loadMe]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
    setMemberships([]);
  }, []);

  const refreshMe = useCallback(async () => {
    if (token) await loadMe(token);
  }, [token, loadMe]);

  return (
    <AuthContext.Provider value={{ token, user, memberships, loading, login, register, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de um AuthProvider.");
  return ctx;
}
