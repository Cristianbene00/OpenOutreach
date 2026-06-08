import type { ReactNode } from "react";

const STATUS_STYLES: Record<string, string> = {
  connected: "bg-green-100 text-green-800",
  pending_login: "bg-amber-100 text-amber-800",
  pending_approval: "bg-amber-100 text-amber-800",
  expired: "bg-red-100 text-red-800",
  checkpoint: "bg-red-100 text-red-800",
  error: "bg-red-100 text-red-800",
  not_configured: "bg-gray-100 text-gray-600",
  approved: "bg-blue-100 text-blue-800",
  sent: "bg-green-100 text-green-800",
  rejected: "bg-gray-200 text-gray-600",
  failed: "bg-red-100 text-red-800",
};

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-700";
  return <span className={`badge ${cls}`}>{status.replace(/_/g, " ")}</span>;
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <div className="mb-4">
      <label className="label">{label}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-gray-500">{hint}</p>}
    </div>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-20 text-gray-400">
      Loading…
    </div>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <p className="mt-2 text-sm text-red-600">{children}</p>;
}
