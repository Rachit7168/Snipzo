const COLORS: Record<string, string> = {
  complete: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-red-500/15 text-red-300",
  queued: "bg-neutral-700/60 text-neutral-300",
};

export default function StatusBadge({ status }: { status: string }) {
  const color = COLORS[status] ?? "bg-yellow-500/15 text-yellow-300";
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>{status}</span>;
}
