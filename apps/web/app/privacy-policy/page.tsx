import { LegalDocument } from "@/components/LegalDocument";

export default function PrivacyPolicyPage() {
  return (
    <LegalDocument title="Privacy Policy" lastUpdated="[TBD — set on legal review]">
      <section>
        <h2>1. Who we are</h2>
        <p>
          INNER is operated by <strong>[Company legal name — TBD]</strong>, registered at{" "}
          <strong>[registered address — TBD]</strong>, the data controller for the personal data described below.
        </p>
      </section>

      <section>
        <h2>2. What we collect</h2>
        <p>
          <strong>Contact data.</strong> The email address you provide at checkout, used to deliver your report and,
          if you opt in, future emails.
        </p>
        <p>
          <strong>Assessment data.</strong> Your answers (multiple-choice, scale, and any free-text responses), the
          dimension scores and profile result computed from them, and the report we generate for you. Free-text
          answers are encrypted at rest and are never included in aggregate analytics.
        </p>
        <p>
          <strong>Technical data.</strong> A functional session cookie that lets you resume an in-progress
          assessment and links a purchase to your results (see Section 7). We also store a salted hash — not the raw
          value — of your IP address and browser user-agent, for fraud and abuse prevention.
        </p>
        <p>
          <strong>Usage data.</strong> Anonymized product-analytics events (e.g. which step of an assessment you
          reached), tied to your anonymous session rather than your identity.
        </p>
        <p>
          <strong>Payment data.</strong> Handled entirely by Stripe, our payment processor. We receive confirmation
          that a payment succeeded and a reference id — never your card number.
        </p>
      </section>

      <section>
        <h2>3. How we use AI</h2>
        <p>
          Some of your assessment answers are sent to Anthropic&apos;s Claude API to generate adaptive follow-up
          questions and to draft the narrative sections of your report. This processing is used only to generate
          your questions and report — it is not used to build an advertising profile of you.
        </p>
      </section>

      <section>
        <h2>4. Why we process your data (legal basis)</h2>
        <ul>
          <li>
            <strong>Performance of a contract:</strong> generating and delivering the report you paid for.
          </li>
          <li>
            <strong>Consent:</strong> sending you marketing emails about new INNER experiences (you opt in
            separately from your purchase, and can withdraw consent at any time).
          </li>
          <li>
            <strong>Legitimate interest:</strong> fraud and abuse prevention, and understanding product usage in
            aggregate.
          </li>
        </ul>
      </section>

      <section>
        <h2>5. Who we share data with</h2>
        <p>We use the following processors to run the service. Each only receives what it needs to do its job:</p>
        <ul>
          <li>
            <strong>Stripe</strong> — payment processing.
          </li>
          <li>
            <strong>Resend</strong> — sending your report and other transactional/marketing email.
          </li>
          <li>
            <strong>Anthropic</strong> — AI generation of adaptive questions and report content (Section 3).
          </li>
          <li>
            <strong>[Hosting / infrastructure provider — TBD]</strong> — running the application and database.
          </li>
        </ul>
        <p>We do not sell your personal data.</p>
      </section>

      <section>
        <h2>6. How long we keep it</h2>
        <p>
          If you request deletion (Section 8), we hard-delete your identity and assessment data outright. Records
          we&apos;re required to keep for tax and accounting purposes are retained with personal details stripped
          down to what invoicing legally requires. Aggregate analytics events are anonymized rather than deleted, so
          the counts they represent stay accurate.
        </p>
      </section>

      <section>
        <h2>7. Cookies</h2>
        <p>
          We use one essential cookie, <code>inner_sid</code>, to identify your anonymous session so you can resume
          an assessment and so a purchase can be linked to your results. It&apos;s set for up to 180 days and is not
          used for third-party advertising. A separate session cookie is set only for admin users of the platform.
        </p>
      </section>

      <section>
        <h2>8. Your rights</h2>
        <p>
          Depending on where you live, you may have the right to access, export, or delete the personal data we hold
          about you. You can exercise these yourself, without contacting us, at{" "}
          <a href="/privacy" className="underline">
            our self-serve privacy page
          </a>
          — we verify the request against your email before acting on it, and it works the same whether or not we
          actually hold data for that address.
        </p>
      </section>

      <section>
        <h2>9. Children</h2>
        <p>
          <strong>[Minimum age — TBD, see Terms of Service Section 4.]</strong> INNER is not directed at children,
          and we do not knowingly collect personal data from anyone below the applicable minimum age.
        </p>
      </section>

      <section>
        <h2>10. International data transfers</h2>
        <p>
          <strong>[TBD — depends on final hosting/processor locations and applicable safeguards.]</strong>
        </p>
      </section>

      <section>
        <h2>11. Changes to this policy</h2>
        <p>
          We may update this policy as the product changes. Material changes will be reflected in the &quot;Last
          updated&quot; date above.
        </p>
      </section>

      <section>
        <h2>12. Contact</h2>
        <p>
          Questions about this policy, or about your data: <strong>[contact email — TBD]</strong>.
        </p>
      </section>
    </LegalDocument>
  );
}
