import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen" style={{ background: "#111827" }}>
      <Sidebar />
      <Topbar />
      {/* Content: offset by sidebar width + topbar height */}
      <main className="ml-60 pt-14">
        <div className="mx-auto max-w-screen-xl px-6 py-8">{children}</div>
      </main>
    </div>
  );
}
