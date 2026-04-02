"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const { error: authError } = await supabase.auth.signInWithPassword({ email, password })
      if (authError) throw authError;
      router.push("/research");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Sign in failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center bg-[#111827] px-4">
      {/* Dot grid background */}
      <div className="bg-grid absolute inset-0 opacity-40" />

      {/* Vignette */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% 50%, transparent 40%, #111827 100%)",
        }}
      />

      <div className="relative z-10 w-full max-w-sm animate-fade-up">
        {/* Logo / wordmark */}
        <div className="mb-8 text-center">
          <div className="mb-3 flex items-center justify-center gap-3">
            <div
              className="flex h-9 w-9 items-center justify-center rounded"
              style={{ background: "#1e3a8a" }}
            >
              <span
                className="text-sm font-semibold tracking-widest text-white"
                style={{ fontFamily: "var(--font-jetbrains-mono)" }}
              >
                KC
              </span>
            </div>
            <span
              className="text-lg font-medium tracking-[0.15em] text-white uppercase"
            >
              Kancil Capital
            </span>
          </div>
          <p
            className="text-xs tracking-wider uppercase"
            style={{ color: "#6b7280" }}
          >
            University of Manchester Investment Fund
          </p>
        </div>

        {/* Card */}
        <div
          className="relative overflow-hidden rounded-lg border p-6"
          style={{
            background: "#1f2937",
            borderColor: "#374151",
            borderLeftWidth: "3px",
            borderLeftColor: "#3b82f6",
          }}
        >
          <h1 className="mb-1 text-base font-medium text-white">
            Sign in to your account
          </h1>
          <p className="mb-6 text-xs" style={{ color: "#9ca3af" }}>
            Authorised personnel only
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="email"
                className="text-xs font-medium uppercase tracking-wider"
                style={{ color: "#9ca3af" }}
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyst@kancil.ac.uk"
                className="rounded border px-3 py-2.5 text-sm text-white outline-none transition-colors placeholder:text-[#4b5563] focus:border-[#3b82f6]"
                style={{
                  background: "#111827",
                  borderColor: "#374151",
                }}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="password"
                className="text-xs font-medium uppercase tracking-wider"
                style={{ color: "#9ca3af" }}
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="rounded border px-3 py-2.5 text-sm text-white outline-none transition-colors placeholder:text-[#4b5563] focus:border-[#3b82f6]"
                style={{
                  background: "#111827",
                  borderColor: "#374151",
                }}
              />
            </div>

            {error && (
              <p className="rounded border border-[#7f1d1d] bg-[#1f0a0a] px-3 py-2 text-xs text-[#ef4444]">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-1 flex h-10 items-center justify-center gap-2 rounded text-sm font-medium text-white transition-opacity disabled:opacity-60"
              style={{ background: "#3b82f6" }}
            >
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Signing in…
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>
        </div>

        <p
          className="mt-6 text-center text-xs"
          style={{ color: "#4b5563" }}
        >
          Access is by invitation only.{" "}
          <span style={{ color: "#6b7280" }}>Contact the CIO for access.</span>
        </p>
      </div>
    </main>
  );
}
