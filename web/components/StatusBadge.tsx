import { Badge, type BadgeTone } from "@/components/ui";

const TONES: Record<string, BadgeTone> = {
  complete: "success",
  succeeded: "success",
  published: "success",
  scheduled: "brand",
  failed: "danger",
  queued: "neutral",
};

export default function StatusBadge({ status }: { status: string }) {
  return <Badge tone={TONES[status] ?? "warning"}>{status}</Badge>;
}
