"use client";

import { usePathname } from "next/navigation";

const pageTitles: Record<string, string> = {
  "/research": "Research",
  "/calendar": "Earnings Calendar",
  "/news": "News Feed",
};

function getTitle(pathname: string): string {
  // Exact match first
  if (pageTitles[pathname]) return pageTitles[pathname];
  // Research sub-pages
  if (pathname.startsWith("/research/")) {
    const ticker = pathname.split("/")[2];
    return ticker ? ticker.toUpperCase() : "Research";
  }
  return "Kancil Capital";
}

export function Topbar() {
  const pathname = usePathname();
  const title = getTitle(pathname);

  return (
    <header
      className="fixed left-60 right-0 top-0 flex h-14 items-center justify-between border-b px-6"
      style={{ background: "#1f2937", borderColor: "#374151", zIndex: 30 }}
    >
      <h1 className="text-sm font-medium text-white">{title}</h1>

      <div className="flex items-center gap-3" />
    </header>
  );
}
