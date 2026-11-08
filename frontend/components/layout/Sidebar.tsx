"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BarChart2, Calendar, Newspaper, List, CircleUser, LogOut } from "lucide-react";
import { supabase } from "@/lib/supabaseClient";

const navItems = [
  { label: "Research", href: "/research", icon: BarChart2 },
  { label: "Calendar", href: "/calendar", icon: Calendar },
  { label: "News", href: "/news", icon: Newspaper },
  { label: "Tickers", href: "/tickers", icon: List },
];

export function Sidebar() {
  const pathname = usePathname();
  const [email, setEmail] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
  }, []);

  async function handleSignOut() {
    setSigningOut(true);
    await supabase.auth.signOut();
    // Full page load, not router.replace: it also clears the in-memory SWR cache,
    // so the next person on a shared computer doesn't see this user's data.
    window.location.replace("/login");
  }

  return (
    <aside
      className="fixed left-0 top-0 flex h-screen w-60 flex-col border-r"
      style={{ background: "#1f2937", borderColor: "#374151" }}
    >
      {/* Wordmark */}
      <div className="flex items-center gap-3 border-b px-4 py-5" style={{ borderColor: "#374151" }}>
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded"
          style={{ background: "#1e3a8a" }}
        >
          <span
            className="text-xs font-semibold tracking-widest text-white"
            style={{ fontFamily: "var(--font-jetbrains-mono)" }}
          >
            KC
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-medium tracking-wide text-white">
            Kancil Capital
          </span>
          <span className="text-[10px] uppercase tracking-widest" style={{ color: "#6b7280" }}>
            Research Terminal
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 px-2 pt-4">
        <p
          className="mb-1 px-2 text-[10px] font-medium uppercase tracking-widest"
          style={{ color: "#6b7280" }}
        >
          Navigation
        </p>
        {navItems.map(({ label, href, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-3 rounded px-2 py-2 text-sm transition-colors"
              style={{
                color: active ? "#f9fafb" : "#9ca3af",
                background: active ? "#374151" : "transparent",
                borderLeft: active ? "2px solid #3b82f6" : "2px solid transparent",
              }}
            >
              <Icon size={15} strokeWidth={active ? 2 : 1.5} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* User */}
      <div className="border-t px-4 py-4" style={{ borderColor: "#374151" }}>
        <div className="flex items-center gap-3">
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
            style={{ background: "#374151" }}
          >
            <CircleUser size={16} style={{ color: "#9ca3af" }} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-white">{email ?? "—"}</p>
            <span
              className="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider"
              style={{ background: "#1e3a8a", color: "#93c5fd" }}
            >
              Analyst
            </span>
          </div>
          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            aria-label="Sign out"
            title="Sign out"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded transition-colors hover:bg-[#374151] disabled:opacity-50"
            style={{ color: "#9ca3af" }}
          >
            <LogOut size={15} strokeWidth={1.5} />
          </button>
        </div>
      </div>
    </aside>
  );
}
