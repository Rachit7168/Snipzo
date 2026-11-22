"use client";

import { useState, type FormEvent } from "react";

import { apiFetch } from "@/lib/api";

export default function TakedownPage() {
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiFetch<{ id: string }>("/takedown", undefined, {
        method: "POST",
        body: JSON.stringify({
          reporter_name: form.get("reporter_name"),
          reporter_email: form.get("reporter_email"),
          content_url: form.get("content_url"),
          original_url: form.get("original_url") || null,
          details: form.get("details"),
          good_faith: form.get("good_faith") === "on",
        }),
      });
      setDone(result.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit the request.");
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-3xl font-bold">Copyright &amp; takedown</h1>
      <p className="text-neutral-400">
        If content processed or published with Snipzo infringes your copyright, send a notice below. We
        review notices within 2 business days, disable the content while we investigate, and notify the
        account owner, who may send a counter-notice.
      </p>
      {done ? (
        <p className="card text-emerald-300">Received. Reference: {done}</p>
      ) : (
        <form onSubmit={onSubmit} className="card space-y-3">
          <input className="input" name="reporter_name" placeholder="Your name" required />
          <input className="input" name="reporter_email" type="email" placeholder="Your email" required />
          <input className="input" name="content_url" placeholder="URL of the infringing Short" required />
          <input className="input" name="original_url" placeholder="URL of your original work (optional)" />
          <textarea className="input min-h-28" name="details" placeholder="Describe the work and the infringement" required />
          <label className="flex items-start gap-2 text-sm text-neutral-300">
            <input type="checkbox" name="good_faith" className="mt-1 accent-yellow-400" required />
            I believe in good faith that this use is not authorized by the copyright owner, its agent, or
            the law, and the information in this notice is accurate.
          </label>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button className="btn w-full">Send notice</button>
        </form>
      )}
    </div>
  );
}
