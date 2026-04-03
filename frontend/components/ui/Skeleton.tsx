interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ className = "", style }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded ${className}`}
      style={{ background: "#374151", ...style }}
    />
  );
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-lg border p-5 ${className}`}
      style={{ background: "#1F2937", borderColor: "#374151" }}
    >
      <Skeleton className="mb-4 h-3 w-24" />
      <Skeleton className="mb-3 h-8 w-full" />
      <Skeleton className="mb-2 h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}

export function SkeletonChart({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-lg border p-5 ${className}`}
      style={{ background: "#1F2937", borderColor: "#374151" }}
    >
      <div className="mb-4 flex items-center justify-between">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <Skeleton className="w-full" style={{ height: 260 }} />
    </div>
  );
}
