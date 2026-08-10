const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:3000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Cliente HTTP fino para a API do OgrowNT. Anexa o JWT (armazenado no
// localStorage, ver lib/auth.ts) em toda chamada exceto login/registro.
// Sem WebSocket/real-time: o Inbox atualiza por polling (ver InboxView) -
// simples e suficiente ate existir infraestrutura de tempo real de fato.
export async function apiFetch<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json");
  if (token) headers.set("authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (res.status === 204) return undefined as T;

  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(res.status, body?.error ?? `Erro ${res.status}`);
  }
  return body as T;
}
