export const metadata = { title: "Privacy policy · Snipzo" };

const contact = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "privacy@example.com";

export default function PrivacyPage() {
  return (
    <article className="prose-invert mx-auto max-w-3xl space-y-4 text-ink-muted">
      <h1 className="text-3xl font-bold text-ink">Privacy policy</h1>
      <p className="text-sm text-ink-subtle">Template for operators. Review with counsel before launch.</p>
      <h2 className="text-xl font-semibold text-ink">What we collect</h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>Account data: email, name, and a salted password hash.</li>
        <li>Videos you upload, their transcripts, and the Shorts we generate.</li>
        <li>If you connect YouTube: your channel ID and title, and OAuth tokens (encrypted at rest).</li>
        <li>Billing status from Stripe (we never see or store full card numbers).</li>
      </ul>
      <h2 className="text-xl font-semibold text-ink">How we use it</h2>
      <p>
        Only to provide the service: transcribe and edit your videos, publish to channels you connect,
        and enforce plan limits. Source videos are deleted automatically after the retention window
        (default 14 days). Transcripts may be sent to AI providers (for example Anthropic) to pick
        highlights and write metadata, if the operator enables them.
      </p>
      <h2 className="text-xl font-semibold text-ink">Google user data</h2>
      <p>
        Snipzo&apos;s use of information received from Google APIs adheres to the{" "}
        <a className="text-brand-text hover:underline" href="https://developers.google.com/terms/api-services-user-data-policy">
          Google API Services User Data Policy
        </a>
        , including the Limited Use requirements. We request YouTube upload and read-only scopes to
        list your own uploads and publish Shorts you ask us to publish. We do not sell this data or use
        it for advertising. You can disconnect at any time from the Channels page or at{" "}
        <a className="text-brand-text hover:underline" href="https://myaccount.google.com/permissions">
          myaccount.google.com/permissions
        </a>
        ; disconnecting deletes the stored tokens.
      </p>
      <h2 className="text-xl font-semibold text-ink">Deletion</h2>
      <p>
        Delete a project to remove its source, transcript, and renders. To delete your account, email{" "}
        {contact}.
      </p>
    </article>
  );
}
