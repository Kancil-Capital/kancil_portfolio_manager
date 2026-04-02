import { supabase } from "@/lib/supabaseClient";

// Base URL is empty — all /api/* calls are proxied to the backend via next.config.ts rewrites.
const BASE = "";

async function getAuthHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeader = await getAuthHeader();
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, init?: RequestInit) => apiFetch<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body: unknown, init?: RequestInit) =>
    apiFetch<T>(path, { ...init, method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown, init?: RequestInit) =>
    apiFetch<T>(path, { ...init, method: "PATCH", body: JSON.stringify(body) }),
};
