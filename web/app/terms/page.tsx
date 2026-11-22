export const metadata = { title: "Terms of service · Snipzo" };

export default function TermsPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-4 text-ink-muted">
      <h1 className="text-3xl font-bold text-ink">Terms of service</h1>
      <p className="text-sm text-ink-subtle">Template for operators. Review with counsel before launch.</p>
      <ol className="list-decimal space-y-3 pl-6">
        <li>
          <strong className="text-ink">Your content.</strong> You may only upload, import, or publish
          content you own or have the rights to use. You confirm this each time you upload or publish.
          You keep ownership of your content and grant Snipzo a limited license to process it to provide
          the service.
        </li>
        <li>
          <strong className="text-ink">No third-party downloads.</strong> Snipzo does not download
          videos from YouTube or other platforms on your behalf unless they belong to your connected
          channel.
        </li>
        <li>
          <strong className="text-ink">Platform rules.</strong> When you publish to YouTube you must
          follow the YouTube Terms of Service and Community Guidelines, including disclosing realistic
          altered or synthetic content.
        </li>
        <li>
          <strong className="text-ink">Plans and billing.</strong> Paid plans renew monthly through
          Stripe until cancelled. Usage limits are listed on the billing page.
        </li>
        <li>
          <strong className="text-ink">Takedowns and termination.</strong> We remove content after valid
          copyright notices and may suspend repeat infringers. See the takedown page.
        </li>
        <li>
          <strong className="text-ink">No warranty.</strong> AI-selected clips, captions, and metadata
          can be wrong. Review before publishing.
        </li>
      </ol>
    </article>
  );
}
