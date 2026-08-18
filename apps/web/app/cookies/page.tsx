import { LegalDocument } from "@/components/LegalDocument";

export default function CookiesPage() {
  return (
    <LegalDocument title="Cookie Policy" lastUpdated="[TBD — set on legal review]">
      <section>
        <h2>1. What this page covers</h2>
        <p>
          INNER uses a small number of first-party cookies to make the product work — resuming an in-progress
          assessment, linking a purchase to your results, and keeping an admin signed in. We do not use
          advertising, tracking, or analytics cookies from any third party, and no cookie here is used to build an
          advertising profile or to track you across other websites.
        </p>
      </section>

      <section>
        <h2>2. Cookies we set</h2>
        <table className="mt-3 w-full border-collapse text-left text-[14px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)]">
              <th className="py-2 pr-3 font-medium text-[var(--inner-ink)]">Cookie</th>
              <th className="py-2 pr-3 font-medium text-[var(--inner-ink)]">Purpose</th>
              <th className="py-2 font-medium text-[var(--inner-ink)]">Duration</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-[var(--inner-line)] align-top">
              <td className="py-2 pr-3">
                <code>inner_sid</code>
              </td>
              <td className="py-2 pr-3">
                Identifies your anonymous session so you can resume an assessment in progress and so a purchase can
                be linked back to your results. Also the identifier our first-party product analytics (completion
                rates, funnel steps) are recorded against — never sold or shared, and never used for advertising.
              </td>
              <td className="py-2">180 days</td>
            </tr>
            <tr className="border-b border-[var(--inner-line)] align-top">
              <td className="py-2 pr-3">
                <code>inner_access</code>
              </td>
              <td className="py-2 pr-3">
                Set only after you request a secure access link by email, so you can view your purchased reports
                without re-entering it every time.
              </td>
              <td className="py-2">180 days</td>
            </tr>
            <tr className="align-top">
              <td className="py-2 pr-3">
                <code>inner_admin_session</code>
              </td>
              <td className="py-2 pr-3">Keeps an INNER team member signed in to the internal admin panel. Not set for regular visitors.</td>
              <td className="py-2">12 hours</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>3. Why we don&apos;t ask for cookie consent on every visit</h2>
        <p>
          Every cookie above is strictly necessary to operate the specific feature it supports — resuming your
          assessment, retrieving your own purchased report, or securing the admin panel — and none of them is used
          for advertising, cross-site tracking, or building a profile of you. Under most cookie-consent frameworks,
          strictly-necessary cookies like these don&apos;t require a consent banner. If that changes as this policy
          gets a full legal review, this page and the site&apos;s behavior will be updated together.
        </p>
      </section>

      <section>
        <h2>4. Managing cookies</h2>
        <p>
          You can block or delete cookies at any time through your browser settings. Because <code>inner_sid</code>{" "}
          is how an in-progress assessment is resumed and how a completed purchase is linked back to your results,
          blocking it means a fresh anonymous session starts on your next visit and any unlinked purchase can only
          be recovered through the{" "}
          <a href="/access" className="underline">
            report access page
          </a>{" "}
          using the email you purchased with.
        </p>
      </section>

      <section>
        <h2>5. More on how we handle your data</h2>
        <p>
          This page covers cookies specifically. For everything else — what we collect, why, how long we keep it,
          and how to access, export, or delete it — see our{" "}
          <a href="/privacy-policy" className="underline">
            Privacy Policy
          </a>{" "}
          and{" "}
          <a href="/privacy" className="underline">
            self-serve privacy page
          </a>
          .
        </p>
      </section>
    </LegalDocument>
  );
}
