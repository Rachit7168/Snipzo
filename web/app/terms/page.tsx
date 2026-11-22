export const metadata = { title: "Terms of service · Snipzo" };

export default function TermsPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-4 text-neutral-300">
      <h1 className="text-3xl font-bold text-white">Terms of service</h1>
      <p className="text-sm text-neutral-500">Template for operators. Review with counsel before launch.</p>
      <ol className="list-decimal space-y-3 pl-6">
        <li>
          <strong className="text-white">Your content.</strong> You may only upload, import, or publish
          content you own or have the rights to use. You confirm this each time you upload or publish.
          You keep ownership of your content and grant Snipzo a limited license to process it to provide
          the service.
        </li>
        <li>
          <strong className="text-white">No third-party downloads.</strong> Snipzo does not download
          videos from YouTube or other platforms on your behalf unless they belong to your connected
          channel.
        </li>
        <li>
          <strong className="text-white">Platform rules.</strong> When you publish to YouTube you must
          follow the YouTube Terms of Service and Community Guidelines, including disclosing realistic
          altered or synthetic content.
        </li>
        <li>
          <strong className="text-white">Plans and billing.</strong> Paid plans renew monthly through
          Stripe until cancelled. Usage limits are listed on the billing page.
        </li>
        <li>
          <strong className="text-white">Takedowns and termination.</strong> We remove content after valid
          copyright notices and may suspend repeat infringers. See the takedown page.
        </li>
        <li>
          <strong className="text-white">No warranty.</strong> AI-selected clips, captions, and metadata
          can be wrong. Review before publishing.
        </li>
      </ol>
    </article>
  );
}
