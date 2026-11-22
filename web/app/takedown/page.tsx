"use client";

import { useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import { Alert, Button, Card, Checkbox, Input, Textarea } from "@/components/ui";
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
      <h1 className="text-3xl font-bold tracking-tight text-ink">Copyright &amp; takedown</h1>
      <p className="text-sm leading-relaxed text-ink-muted">
        If content processed or published with Snipzo infringes your copyright, send a notice below. We
        review notices within 2 business days, disable the content while we investigate, and notify the
        account owner, who may send a counter-notice.
      </p>
      {done ? (
        <Alert tone="success" title="Notice received">
          Reference: <span className="font-mono">{done}</span>
        </Alert>
      ) : (
        <Card>
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            <Input
              id="td-name"
              name="reporter_name"
              label="Your name"
              placeholder="Your name"
              required
              error={fieldErrors.reporter_name}
            />
            <Input
              id="td-email"
              name="reporter_email"
              type="email"
              label="Your email"
              placeholder="you@example.com"
              required
              error={fieldErrors.reporter_email}
            />
            <Input
              id="td-content-url"
              name="content_url"
              label="URL of the infringing Short"
              placeholder="https://..."
              required
              error={fieldErrors.content_url}
            />
            <Input
              id="td-original-url"
              name="original_url"
              label="URL of your original work (optional)"
              placeholder="https://..."
              error={fieldErrors.original_url}
            />
            <Textarea
              id="td-details"
              name="details"
              label="Description of the infringement"
              placeholder="Describe the work and the infringement"
              required
              error={fieldErrors.details}
            />
            <Checkbox
              name="good_faith"
              required
              label="I believe in good faith that this use is not authorized by the copyright owner, its agent, or the law, and the information in this notice is accurate."
              error={fieldErrors.good_faith}
            />
            {formError && <Alert tone="error">{formError}</Alert>}
            <Button type="submit" fullWidth loading={busy}>
              {busy ? "Sending..." : "Send notice"}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
