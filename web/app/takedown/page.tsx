"use client";

import { useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import { apiFetch } from "@/lib/api";
import { mapApiError } from "@/lib/errors";

export default function TakedownPage() {
  const { showToast } = useToast();
  const [done, setDone] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiFetch<{ id: string }>("/takedown", undefined, {
        method: "POST",
        body: JSON.stringify({
          reporter_name: String(form.get("reporter_name") || ""),
          reporter_email: String(form.get("reporter_email") || ""),
          content_url: String(form.get("content_url") || ""),
          original_url: String(form.get("original_url") || "").trim() || null,
          details: String(form.get("details") || ""),
          good_faith: form.get("good_faith") === "on",
        }),
      });
      setDone(result.id);
    } catch (err) {
      const mapped = mapApiError(err, "Could not submit the request.");
      if (mapped.fields && Object.keys(mapped.fields).length > 0) {
        setFieldErrors(mapped.fields);
      } else {
        setFormError(mapped.message);
        showToast({ title: mapped.title, message: mapped.message, tone: "error" });
      }
    } finally {
      setBusy(false);
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
        <form onSubmit={onSubmit} noValidate className="card space-y-3">
          <div className="space-y-1">
            <label htmlFor="td-name" className="block text-xs font-medium text-neutral-300">
              Your name
            </label>
            <input
              id="td-name"
              className="input"
              name="reporter_name"
              placeholder="Your name"
              required
              aria-invalid={Boolean(fieldErrors.reporter_name)}
              aria-describedby={fieldErrors.reporter_name ? "td-name-error" : undefined}
            />
            {fieldErrors.reporter_name && (
              <p id="td-name-error" className="text-xs text-red-400">
                {fieldErrors.reporter_name}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label htmlFor="td-email" className="block text-xs font-medium text-neutral-300">
              Your email
            </label>
            <input
              id="td-email"
              className="input"
              name="reporter_email"
              type="email"
              placeholder="you@example.com"
              required
              aria-invalid={Boolean(fieldErrors.reporter_email)}
              aria-describedby={fieldErrors.reporter_email ? "td-email-error" : undefined}
            />
            {fieldErrors.reporter_email && (
              <p id="td-email-error" className="text-xs text-red-400">
                {fieldErrors.reporter_email}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label htmlFor="td-content-url" className="block text-xs font-medium text-neutral-300">
              URL of the infringing Short
            </label>
            <input
              id="td-content-url"
              className="input"
              name="content_url"
              placeholder="https://..."
              required
              aria-invalid={Boolean(fieldErrors.content_url)}
              aria-describedby={fieldErrors.content_url ? "td-content-url-error" : undefined}
            />
            {fieldErrors.content_url && (
              <p id="td-content-url-error" className="text-xs text-red-400">
                {fieldErrors.content_url}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label htmlFor="td-original-url" className="block text-xs font-medium text-neutral-300">
              URL of your original work (optional)
            </label>
            <input
              id="td-original-url"
              className="input"
              name="original_url"
              placeholder="https://..."
              aria-invalid={Boolean(fieldErrors.original_url)}
              aria-describedby={fieldErrors.original_url ? "td-original-url-error" : undefined}
            />
            {fieldErrors.original_url && (
              <p id="td-original-url-error" className="text-xs text-red-400">
                {fieldErrors.original_url}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label htmlFor="td-details" className="block text-xs font-medium text-neutral-300">
              Description of the infringement
            </label>
            <textarea
              id="td-details"
              className="input min-h-28"
              name="details"
              placeholder="Describe the work and the infringement"
              required
              aria-invalid={Boolean(fieldErrors.details)}
              aria-describedby={fieldErrors.details ? "td-details-error" : undefined}
            />
            {fieldErrors.details && (
              <p id="td-details-error" className="text-xs text-red-400">
                {fieldErrors.details}
              </p>
            )}
          </div>

          <label className="flex items-start gap-2 text-sm text-neutral-300">
            <input
              type="checkbox"
              name="good_faith"
              className="mt-1 accent-yellow-400"
              required
              aria-invalid={Boolean(fieldErrors.good_faith)}
            />
            I believe in good faith that this use is not authorized by the copyright owner, its agent, or
            the law, and the information in this notice is accurate.
          </label>
          {fieldErrors.good_faith && <p className="text-xs text-red-400">{fieldErrors.good_faith}</p>}

          {formError && (
            <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {formError}
            </div>
          )}

          <button className="btn w-full" disabled={busy}>
            {busy ? "Sending..." : "Send notice"}
          </button>
        </form>
      )}
    </div>
  );
}
