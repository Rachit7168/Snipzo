"use client";

import { useParams } from "next/navigation";
import { useSession } from "next-auth/react";

import ClipEditor from "@/components/ClipEditor";

export default function ClipEditorPage() {
  const { id, clipId } = useParams<{ id: string; clipId: string }>();
  const { data: session } = useSession();
  if (!session?.accessToken) return <p className="text-neutral-400">Loading...</p>;
  return <ClipEditor projectId={id} clipId={clipId} token={session.accessToken} />;
}
