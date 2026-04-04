import { supabase } from "@/lib/supabaseClient";

async function getAuthHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// orval v8 expects the mutator to return { data, status, headers }
export const fetcher = async <T>(
  url: string,
  options?: RequestInit,
): Promise<T> => {
  const authHeader = await getAuthHeader();
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
      ...options?.headers,
    },
  });

  const body = res.ok
    ? res.status === 204 ? null : await res.json()
    : await res.text();

  if (!res.ok) {
    throw new Error(`API ${res.status}: ${body}`);
  }

  return { data: body, status: res.status, headers: res.headers } as T;
};
